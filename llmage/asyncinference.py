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
		today = env.get_business_date(sor)
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
		if d.status != 'SUCCEEDED':
			e = Exception(f'resp={d} not success')
			raise e
		responsed_seconds = time.time() - start_timestamp
		finish_seconds = response_seconds
		llmusage = DictObject()
		llmusage.id = luid
		llmusage.llmid = llm.id
		llmusage.use_date = curDateString()
		llmusage.use_time = timestampstr()
		llmusage.userid = callerid
		llmusage.usage = json.dumps(usage)
		llmusage.ioinfo = json.dumps({
			"input": params_kw
		})
		llmusage.taskid = d.taskid
		llmusage.transno = params_kw.transno
		llmusage.responsed_seconds = responsed_seconds
		llmusage.finish_seconds = finish_seconds
		llmusage.status = 'CREATED'
		llmusage.userorgid = callerorgid
		llmusage.ownerid = llm.orgid
		b = json.dumps(d, ensure_ascii=False)
		yield b
		await write_llmusage(llmusage)
		await llm_accounting(request, llmusage)
		# if llm.callbackurl:
		#	return
		apinames = [ name.strip() for name in llm.query_apiname.split(',') ]
		asyncio.create_task(query_task_status(request, llm.upappid, 
								apinames, luid, userid, d.taskid))

	except Exception as e:
		exception(f'{e=},{format_exc()}')
		estr = erase_apikey(e)
		ed = {"error": f"ERROR:{estr}", "status": "FAILED"}
		s = json.dumps(ed)
		s = ''.join(s.split('\n'))
		yield f'{s}\n'
		return

async def add_new_llmusage_output(luid, rzt):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		recs = await sor.R('llmusage', {'id': luid})
		if recs:
			r = recs[0]
			io = json.loads(r.ioinfo)
			out = io.get('output', [])
			out.append(rzt)
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
			status = 'unknown'
			while status != 'SUCCEEDED':
				ns = {'taskid': taskid}
				d = None
				try:
					b = await uapi.call(upappid, apiname, userid, params=ns)
					if isinstance(b, bytes):
						b = b.decode('utf-8')
					d = json.loads(b)
				except Exception as e:
					e = Exception(f'{e}')
					exception(f'{e}')
					changed = {
						'status': 'FAILED',
						'output': {'status': 'FAILED', 'error': str(e)}
					}
					await add_new_llmusage_output(luid, changed)
					return
				rzt = DictObject(**d)
				changed = {
					'status': rzt.status,
					'output': rzt
				}
				if rzt.status == 'SUCCEEDED':
					if llm.ppid:
						try:
							charging = await llm_charging(sor, 
												llm.ppid, llmusage)
							if charging:
								changed.amount = charging.amount
								changed.cost = charging.cost
							else:
								changed.amount = cost = 0.0
						except Exception as e:
							e = Exception(f'{llm.pid} charging error{e}')
							exception(f'{e}')
					else:
						changed.amount = 0
						changed.cost = 0
					await add_new_llmusage_output(luid, changed)
					await llm_accounting(request, llmusage)
				status = rzt.status
				if rzt.status == 'FAILED':
					return
				await asyncio.sleep(0.1)
					
