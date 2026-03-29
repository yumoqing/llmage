import json
import time
import asyncio
from random import randint
from functools import partial
from traceback import format_exc
from sqlor.dbpools import DBPools, get_sor_context
from appPublic.log import debug, exception, error
from appPublic.uniqueID import getID
from appPublic.dictObject import DictObject
from appPublic.timeUtils import curDateString, timestampstr
from appPublic.base64_to_file import base64_to_file, getFilenameFromBase64
from uapi.appapi import UAPI, sor_get_callerid, sor_get_uapi
from ahserver.serverenv import get_serverenv, ServerEnv
from ahserver.filestorage import FileStorage
from .asyncinference import async_uapi_request
from .syncinference import sync_uapi_request
from .accounting import llm_accounting, llm_charging
from .utils import *

async def uapi_request(request, llm, sor, callerid, callerorgid, params_kw=None):
	env = request._run_ns.copy()
	if not params_kw:
		params_kw = env.params_kw
	# callerorgid = await env.get_userorgid()
	# callerid = await env.get_user()
	uapi = UAPI(request, sor=sor)
	userid = await get_owner_userid(sor, llm)
	outlines = []
	txt = ''
	luid = getID()
	try:
		start_timestamp = time.time()
		responsed_seconds = None
		finish_seconds = None
		first = True
		usage = None
		async for l in uapi.stream_linify(llm.upappid, llm.apiname, userid, 
					params=params_kw):
			if first:
				first = False
				responsed_seconds = time.time() - start_timestamp
			if isinstance(l, bytes):
				l = l.decode('utf-8')
			if l[-1] == '\n':
				l = l[:-1]
			debug(f'stream response line={l},{type(l)}')
			l = ''.join(l.split('\n'))
			if l and l != '[DONE]':
				yield_it = False
				d = {}
				try:
					d = json.loads(l)
				except Exception as e:
					debug(f'json.loads({l}) error({e})')
					continue
				if d.get('reasoning_content'):
					txt += d.get('reasoning_content')
					yield_it = True
				if d.get('content'):
					txt = txt + d['content']
					yield_it = True
				if d.get('usage'):
					usage = d['usage']
				d['llmusageid'] = luid
				outlines.append(d)
				yield json.dumps(d) + '\n'
		if usage is None:
			error(f'{llm=} response has not usage')
		finish_seconds = time.time() - start_timestamp
		if responsed_seconds is None:
			responsed_seconds = finish_seconds
		if not usage.get('completion_tokens'):
			usage['completion_tokens'] = len(txt)
		if not usage.get('prompt_tokens'):
			cnt = 0
			if params_kw.prompt:
				cnt += len(params_kw.prompt)
			if params_kw.negitive_prompt:
				cnt += len(params_kw.negitive_promot)
			usage['prompt_tokens'] = cnt
		llmusage = DictObject()
		llmusage.id = luid
		llmusage.llmid = llm.id
		llmusage.use_date = curDateString()
		llmusage.use_time = timestampstr()
		llmusage.userid = callerid
		llmusage.usage = json.dumps(usage)
		llmusage.ioinfo = json.dumps({
			"input": params_kw,
			"output": outlines
		})
		llmusage.transno = params_kw.transno
		llmusage.responsed_seconds = responsed_seconds
		llmusage.finish_seconds = finish_seconds
		llmusage.status = 'SUCCEEDED'
		if llm.ppid and callerorgid:
			try:
				chargings = await llm_charging(sor, llm.ppid, llmusage)
				llmusage.amount = chargings.amount
				llmusage.cost = chargings.cost
			except Exception as e:
				e = Exception(f'{llm.pid} charging error{e}')
				exception(f'{e}')
		else:
			llmusage.amount = 0
			llmusage.cost = 0
		llmusage.userorgid = callerorgid
		llmusage.ownerid = llm.orgid
		llmusage.accounting_status = 'created'
		await write_llmusage(llmusage)
		await llm_accounting(request, llmusage)

	except Exception as e:
		exception(f'{e=},{format_exc()}')
		estr = erase_apikey(e)
		ed = {"error": f"ERROR:{estr}", "status": "FAILED" ,"llmusageid": luid}
		s = json.dumps(ed)
		s = ''.join(s.split('\n'))
		outlines.append(ed)
		yield f'{s}\n'
		#  await write_llmusage(luid, llm, callerid, None, params_kw, outlines, sor)
		return

def b64media2url(request, mediafile):
	env = request._run_ns
	entire_url = env.entire_url
	if mediafile.startswith('data:'):
		try:
			fs = FileStorage()
			fname = getFilenameFromBase64(mediafile)
			fpath = fs._name2path(fname)
			base64_to_file(mediafile, fpath)
			path = fs.webpath(fpath)
			return entire_url('/idfile?path=') + env.quote(path)
		except Exception as e:
			exception(f'{e}\n{format_exc()}')
			return ' '
	if mediafile.startswith('http://') or mediafile.startswith('https://'):
		return mediafile
	url = entire_url('/idfile?path=') + env.quote(mediafile)
	return url

async def inference_generator(request, *args, params_kw=None, **kw):
	env = request._run_ns.copy()
	callerorgid = await env.get_userorgid()
	callerid = await env.get_user()
	async for d in _inference_generator(request, callerid, 
						callerorgid, params_kw=params_kw, **kw):
		yield d

async def _inference_generator(request, callerid, callerorgid, 
							params_kw={}, **kw):
	env = request._run_ns
	if not params_kw:
		params_kw = env.params_kw
	if not params_kw.transno:
		params_kw.transno = getID()
	llmid = params_kw.llmid
	dbname = env.get_module_dbname('llmage')
	db = env.DBPools()
	async with db.sqlorContext(dbname) as sor:
		f = None
		llm = await get_llm(llmid)
		if llm is None:
			errmsg = f'{{"status": "FAILED", "error":"llmid:{llmid}没找到模型"}}\n'
			exception(errmsg)
			yield errmsg
			return
		if not params_kw.model:
			params_kw.model = llm.model
		if params_kw.nostream and llm.stream == 'stream':
			llm.stream = 'sync'
		if llm.stream == 'async':
			if llm.callbackurl:
				cb_url = env.entire_url(llm.callbackurl)
				params_kw.callbackurl = cb_url
			f = partial(async_uapi_request, request, llm, sor, callerid, callerorgid, params_kw=params_kw)
		elif llm.stream == 'sync':
			f = partial(sync_uapi_request, request, llm, sor, callerid, callerorgid, params_kw=params_kw)
		# env.update(llm)
		else:
			uapi = UAPI(request, sor=sor)
			f = partial(uapi_request, request, llm, sor, callerid, callerorgid, params_kw=params_kw)
		async for d in f():
			yield d

async def inference(request, *args, params_kw=None, **kw):
	env = request._run_ns.copy()
	f = partial(inference_generator, request, *args, params_kw=params_kw, **kw)
	return await env.stream_response(request, f)
	
async def llm_query_price(llmid, config_data):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		llms = await sor.R('llm', {'id': llmid})
		if not llms:
			e = Exception(f'id={llmid} llm not founnd')
			exception(f'{e}')
			raise e
		llm = llms[0]
		if llm.ppid is None:	
			e = Exception(f'{llm=} ppid is None')
			exception(f'{e}')
			raise e
		prices = await env.pricing_program_charging(sor, llm.ppid, config_data)
		return prices

async def add_new_llmusage_output(luid, rzt):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		recs = await sor.R('llmusage', {'id': luid})
		if recs:
			r = recs[0]
			io = json.loads(r.ioinfo)
			out = io.get('output', [])
			out.append(out)
			io['output'] = out
			r.ioinfo = json.dumps({
				'input': io.get('input',{}),
				'output': out
			})
			await sor.U('llmusage', r)
			return

async def query_task_status(request, upappid, apinames, luid, userid, taskid):
	async with get_sor_context(env, 'llmage') as sor:
		uapi = UAPI(request, sor)
		for apiname in apinames:
			try:
				ns = {'taskid': taskid}
				b = await uapi.call(upappid, apiname, userid, params=ns)
				if isinstance(b, bytes):
					b = b.decode('utf-8')
				d = json.loads(b)
				rzt = DictObject(**d)
				await add_new_llmusage_output(luid, rzt)
				if rzt.status == 'FAILED':
					return
				if rzt.status == 'SUCCEEDED':
					if llm.ppid:
						try:
							chargings = await llm_charging(sor, 
												llm.ppid, callerid, usage)
							llmusage.amount = chargings.amount
							llmusage.cost = chargings.cost
						except Exception as e:
							e = Exception(f'{llm.pid} charging error{e}')
							exception(f'{e}')
					else:
						llmusage.amount = 0
						llmusage.cost = 0
					await llm_accounting(request, llmusage)
					
			except Exception as e:
				exception(f'{e=},{format_exc()}')
				estr = erase_apikey(e)
				recs = sor.R('llmusage', {'id': luid})
				ed = {"error": f"ERROR:{estr}", "status": "FAILED", 'taskid': taskid}
				await add_new_llmusage_output(luid, ed)
				return

