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
from .accounting import llm_accounting, llm_charging
from .utils import *

async def get_today_asynctask_list(userid):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		today = await env.get_business_date(sor)
		sql = '''select * from llmusage 
where userid=${userid}$ 
	and use_date = ${date}$'''
		recs = await sor.sqlExe(sql, {
			'date': today,
			'userid': userid
		})
		return recs
	return []

async def get_asynctask_status(taskid):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		recs = sor.R('llmusage', {'taskid', taskid})
		if recs:
			r = recs[0]
			io = json.loads(r.ioinfo)
			d = io.get('output', {})
			if isinstance(d, list):
				return d[-1]
			return d
		return {
			'taskid': taskid,
			'status': 'FAILED',
			'error': f'taskid={taskid} not exist'
		}
	return {
		'taskid': taskid,
		'status': 'FAILED',
		'error': f'system error'
	}
	
async def async_uapi_request(request, llm, sor, 
				callerid, callerorgid, params_kw=None):
	env = request._run_ns.copy()
	if not params_kw:
		params_kw = env.params_kw
	# callerorgid = await env.get_userorgid()
	# callerid = await env.get_user()
	uapi = UAPI(request, sor=sor)
	userid = await get_owner_userid(sor, llm)
	b = None
	luid = getID()
	try:
		start_timestamp = time.time()
		if llm.callbackurl:
			params_kw.callbackurl = llm.callbackurl
		
		b = None
		try:
			b = await uapi.call(llm.upappid, llm.apiname, userid, params=params_kw)
		except Exception as e:
			exception(f'{e}')
			raise e
		if isinstance(b, bytes):
			b = b.decode('utf-8')
		debug(f'task submited:{b}')
		d = DictObject(**json.loads(b))
		responsed_seconds = time.time() - start_timestamp
		finish_seconds = responsed_seconds
		llmusage = DictObject()
		llmusage.id = luid
		llmusage.llmid = llm.id
		llmusage.use_date = curDateString()
		llmusage.use_time = timestampstr()
		llmusage.userid = callerid
		llmusage.ioinfo = json.dumps({
			"input": params_kw,
			'output': [d]
		})
		llmusage.taskid = d.taskid
		llmusage.transno = params_kw.transno
		llmusage.responsed_seconds = responsed_seconds
		llmusage.finish_seconds = finish_seconds
		llmusage.status = d.status
		llmusage.userorgid = callerorgid
		llmusage.ownerid = llm.orgid
		llmusage.accounting_status = 'created'
		b = json.dumps(d, ensure_ascii=False)
		yield b
		await write_llmusage(llmusage)
		# if llm.callbackurl:
		#	return
		if d.status == 'FAILED':
			e = Exception(f'resp={d} FFAILED')
			raise e
		asyncio.create_task(query_task_status(request, llm.upappid, 
								llm.query_apiname, luid, userid, d.taskid))
		yield d

	except Exception as e:
		exception(f'{e=},{format_exc()}')
		estr = erase_apikey(e)
		ed = {"error": f"ERROR:{estr}", "status": "FAILED"}
		s = json.dumps(ed)
		s = ''.join(s.split('\n'))
		yield f'{s}\n'
		return

async def add_new_llmusage_output(luid, newd):
	env = ServerEnv()
	newd = newd.copy()
	async with get_sor_context(env, 'llmage') as sor:
		recs = await sor.R('llmusage', {'id': luid})
		if recs:
			r = recs[0]
			io = json.loads(r.ioinfo)
			out = io.get('output', [])
			rzt = newd.get('output')
			if rzt:
				out.append(rzt)
				newd = {k:v for k,v in newd.items() if k != 'output'}
			io['output'] = out
			r.ioinfo = json.dumps(io)
			r.update(newd)
			await sor.U('llmusage', r)
			return
def get_llmusage_last_output(r):
	io = json.loads(r.ioinfo)
	outs = io.get('output', [])
	if len(outs) == 0:
		return None
	d = DictObject(**outs[-1])
	return d

async def query_task_status(request, upappid, apiname, luid, userid, taskid):
	env = request._run_ns
	async with get_sor_context(env, 'llmage') as sor:
		recs = await sor.R('llmusage', {'id': luid})
		if len(recs) == 0:
			e = Exception(f'{luid=} is not found in llmusage')
			exception(f'{e}')
			raise e
		llmusage = recs[0]
		llms = await sor.R('llm', {'id': llmusage.llmid})
		if len(llms) == 0:
			e = Exception(f'{llmusage.llmid=} not found in llm')
			exception(f'{e}')
			raise e
		llm = llms[0]
		lastoutout = get_llmusage_last_output(llmusage)
		if lastoutout and lastoutout.status == 'SUCCEEDED':
			return
		uapi = UAPI(request, sor)
		apinames = apiname.split(',')
		for apiname in apinames:
			status = 'unknown'
			changed = None
			while status != 'SUCCEEDED':
				ns = {'taskid': taskid}
				d = None
				try:
					b = await uapi.call(upappid, apiname, userid, params=ns)
					if isinstance(b, bytes):
						b = b.decode('utf-8')
					d = json.loads(b)
					changed = DictObject(**{
						'status': d['status'],
						'output': d
					})
				except Exception as e:
					exception(f'{e}, {b=}')
					changed = {
						'status': 'FAILED',
						'output': {'status': 'FAILED', 'error': str(e)}
					}
					await add_new_llmusage_output(luid, changed)
					return
				if changed.status == 'SUCCEEDED':
					llmusage.usage = changed.output.usage
					if llm.ppid:
						try:
							charging = await llm_charging(sor, 
												llm.ppid, llmusage)
							if charging:
								changed.amount = charging.amount
								changed.cost = charging.cost
								debug(f'{changed=},{charging=}')
							else:
								changed.amount = cost = 0.0
						except Exception as e:
							e1 = Exception(f'{llm.ppid} charging error{e}, {llm.ppid}, {llmusage=}')
							exception(f'{e}')
							changed.amount = changed.cost = 0
					else:
						changed.amount = 0
						changed.cost = 0
					llmusage.amount = changed.amount
					llmusage.cost   = changed.cost
				await add_new_llmusage_output(luid, changed)
				if changed.status == 'FAILED':
					return
				if changed.status == 'SUCCEEDED':
					if llmusage.accounting_status != 'accounted' \
									and changed.amount > 0.00001:
						try:
							await llm_accounting(request, llmusage)
						except Exception as e:
							debug(f'{changed=} accounting failed,{e=} ')
					return

				await asyncio.sleep(llm.query_period or 30)
				debug(f'{llm.query_period=} seconds will retry, {changed.status=}')
					
