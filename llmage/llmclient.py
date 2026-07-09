import json
import time
import asyncio
from random import randint
from functools import partial
from traceback import format_exc
from appPublic.log import debug, exception, error
from appPublic.uniqueID import getID
from appPublic.dictObject import DictObject
from appPublic.timeUtils import curDateString, timestampstr
from appPublic.base64_to_file import base64_to_file, getFilenameFromBase64
from ahserver.serverenv import get_serverenv, ServerEnv
from ahserver.filestorage import FileStorage
from .asyncinference import async_uapi_request
from .syncinference import sync_uapi_request
from .accounting import llm_accounting, llm_charging
from .utils import *

async def uapi_request(request, llm, callerid, callerorgid, params_kw=None):
	env = request._run_ns.copy()
	if not params_kw:
		params_kw = env.params_kw
	# callerorgid = await env.get_userorgid()
	# callerid = await env.get_user()
	uapi = env.UpAppApi(request)
	userid = await env.uapi_data.get_calluserid(llm.upappid, orgid=llm.ownerid)
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
				yield json.dumps(d, ensure_ascii=False) + '\n'
		if usage is None:
			error(f'{llm=} response has not usage')
		finish_seconds = time.time() - start_timestamp
		if responsed_seconds is None:
			responsed_seconds = finish_seconds
		llmusage = DictObject()
		llmusage.id = luid
		llmusage.llmid = llm.id
		llmusage.use_date = curDateString()
		llmusage.use_time = timestampstr()
		llmusage.userid = callerid
		llmusage.usages = json.dumps(usage, ensure_ascii=False, indent=4)
		debug(f' {usage=}, {type(usage)=}, {llmusage.usages=}')
		ioinfo = {
			"input": params_kw,
			'output': outlines
		}
		webpath = await write_llmio(llmusage.id, ioinfo)
		llmusage.ioinfo = webpath
		llmusage.transno = params_kw.transno
		llmusage.responsed_seconds = responsed_seconds
		llmusage.finish_seconds = finish_seconds
		llmusage.status = 'SUCCEEDED'
		llmusage.userorgid = callerorgid
        llmusage.tenantid = params_kw.get('tenantid', params_kw.get('tentantid'))
		llmusage.ownerid = llm.ownerid
		llmusage.accounting_status = 'created'
		await write_llmusage(llmusage)
	except Exception as e:
		exception(f'{e=},{format_exc()}')
		estr = erase_apikey(e)
		ed = {"error": f"ERROR:{estr}", "status": "FAILED" ,"llmusageid": luid}
		s = json.dumps(ed, ensure_ascii=False)
		s = ''.join(s.split('\n'))
		outlines.append(ed)
		yield f'{s}\n'
		return

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
	catelogid = params_kw.get('llmcatelogid', None)
	f = None
	llm = await get_llm(llmid, catelogid)
	if llm is None:
		errmsg = f'{{"status": "FAILED", "error":"llmid:{llmid}没找到模型"}}\n'
		exception(errmsg)
		yield errmsg
		return
	params_kw.model = llm.model
	if llm.stream == 'async':
		if llm.callbackurl:
			cb_url = env.entire_url(llm.callbackurl)
			params_kw.callbackurl = cb_url
		f = partial(async_uapi_request, request, llm, callerid, callerorgid, params_kw=params_kw)
	elif not params_kw.stream:
		llm.stream = False
		debug(f'---{params_kw.stream=}, {llm.stream=} ---use sync_uapi_request ')
		f = partial(sync_uapi_request, request, llm, callerid, callerorgid, params_kw=params_kw)
	else:
		llm.stream = True
		debug(f'---{params_kw.stream=}, {llm.stream=} ---use uapi_request ')
		f = partial(uapi_request, request, llm, callerid, callerorgid, params_kw=params_kw)
	async for d in f():
		yield d

async def inference(request, *args, params_kw=None, **kw):
	env = request._run_ns.copy()
	f = partial(inference_generator, request, *args, params_kw=params_kw, **kw)
	return await env.stream_response(request, f)
	
