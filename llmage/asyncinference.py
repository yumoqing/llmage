import json
import time
import asyncio
from random import randint
from functools import partial
from traceback import format_exc
from sqlor.dbpools import DBPools, get_sor_context
from appPublic.log import debug, exception, error, critical
from appPublic.uniqueID import getID
from appPublic.dictObject import DictObject
from appPublic.timeUtils import curDateString, timestampstr, timestampAdd
from appPublic.base64_to_file import base64_to_file, getFilenameFromBase64
from ahserver.serverenv import get_serverenv, ServerEnv
from ahserver.filestorage import FileStorage
from .accounting import llm_accounting, llm_charging
from .utils import *

# Global set to keep references to background tasks
_background_tasks = set()

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

async def get_asynctask_status(request, taskid):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		recs = await sor.R('llmusage', {'taskid': taskid})
		if recs:
			r = recs[0]
			output = await get_lastoutput(r.ioinfo)
			t = timestampAdd(r.use_time, 600)
			now = time.time()
			if r.status not in ['UNKNOWN', 'FAILED', 'SUCCEEDED'] and now > t:
				task = asyncio.create_task(query_task_status(request, r.id))
				_background_tasks.add(task)
				task.add_done_callback(_background_tasks.discard)
			return output
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
	
async def async_uapi_request(request, llm, 
				callerid, callerorgid, params_kw=None):
	env = request._run_ns.copy()
	if not params_kw:
		params_kw = env.params_kw
	# callerorgid = await env.get_userorgid()
	# callerid = await env.get_user()
	uapi = env.UpAppApi(request)
	userid = await env.uapi_data.get_calluserid(llm.upappid, orgid=llm.ownerid)
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
			estr = erase_apikey(e)
			ed = {"error": f"ERROR:{estr}", "status": "FAILED"}
			exception(f'{ed}')
			estr = json.dumps(ed, ensure_ascii=False)
			yield f'{estr}\n'
			return
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
		ioinfo = {
			"input": params_kw,
			'output': [d]
		}
		webpath = await write_llmio(llmusage.id, ioinfo)
		llmusage.ioinfo = webpath
		llmusage.taskid = d.taskid
		llmusage.transno = params_kw.transno
		llmusage.responsed_seconds = responsed_seconds
		llmusage.finish_seconds = finish_seconds
		llmusage.status = d.status
		llmusage.userorgid = callerorgid
		llmusage.tenantid = params_kw.get('tenantid', params_kw.get('tentantid'))
		llmusage.ownerid = llm.ownerid
		llmusage.accounting_status = 'created'
		b = json.dumps(d, ensure_ascii=False)
		yield b
		# await write_llmusage(llmusage)
		# if llm.callbackurl:
		#	return
		if d.status == 'FAILED':
			e = Exception(f'resp={d} FFAILED')
			return
		task = asyncio.create_task(query_task_status(request, luid))
		_background_tasks.add(task)
		task.add_done_callback(_background_tasks.discard)

	except Exception as e:
		ed = {"error": f"ERROR:{e}", "status": "FAILED"}
		s = json.dumps(ed, ensure_ascii=False)
		s = ''.join(s.split('\n'))
		exception(s)
		yield f'{s}\n'
		llmusage = DictObject()
		llmusage.id = luid
		llmusage.llmid = llm.id
		llmusage.use_date = curDateString()
		llmusage.use_time = timestampstr()
		llmusage.userid = callerid
		ioinfo = {
			"input": params_kw,
			'output': [ed]
		}
		webpath = await write_llmio(llmusage.id, ioinfo)
		llmusage.ioinfo = webpath
		llmusage.taskid = d.taskid
		llmusage.transno = params_kw.transno
		llmusage.responsed_seconds = responsed_seconds
		llmusage.finish_seconds = finish_seconds
		llmusage.status = 'FAILED'
		llmusage.userorgid = callerorgid
		llmusage.tenantid = params_kw.get('tenantid', params_kw.get('tentantid'))
		llmusage.ownerid = llm.ownerid
		return
	finally:
		await write_llmusage(llmusage)

async def modify_llmusage(ns):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		await sor.U('llmusage', ns.copy())

async def get_llm_llmusage(luid):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		recs = await sor.R('llmusage', {'id': luid})
		if len(recs) == 0:
			e = Exception(f'{luid=} is not found in llmusage')
			exception(f'{e}')
			raise e
		llmusage = recs[0]
		if llmusage.status == 'UNKNOWN':
			return
		if llmusage.status == 'SUCCEEDED':
			return
		if llmusage.status == 'FAILED':
			return
		# Use JOIN to get query_apiname/query_period from llm_api_map
		sql = """select a.id, a.name, a.model, a.upappid, a.ownerid, a.status,
m.apiname, m.query_apiname, m.query_period, m.ppid
from llm a
join llm_api_map m on a.id = m.llmid
where a.id = ${llmid}$ and m.isdefaultcatelog = '1'"""
		llms = await sor.sqlExe(sql, {'llmid': llmusage.llmid})
		if len(llms) == 0:
			e = Exception(f'{llmusage.llmid=} not found in llm/llm_api_map')
			exception(f'{e}')
			raise e
		llm = llms[0]
		return llm, llmusage

async def query_task_status(request, luid, onetime=False):
	env = ServerEnv()
	uapi = env.UpAppApi(request)
	llm, llmusage = await get_llm_llmusage(luid)
	userid = await env.uapi_data.get_calluserid(llm.upappid, orgid=llm.ownerid)
	taskid = llmusage.taskid
	upappid = llm.upappid
	apinames = llm.query_apiname.split(',')

	try:
		for apiname in apinames:
			while True:
				lastoutout = await get_lastoutput(llmusage.ioinfo)
				if lastoutout.get('status', '') in ['UNKNOWN', 'FAILED', 'SUCCEEDED']:
					critical(f"{lastoutout.get('status', '')=}")
					return
				ns = {'taskid': taskid}
				new_output = b = d = None
				try:
					b = await uapi.call(upappid, apiname, userid, params=ns)
					if isinstance(b, bytes):
						b = b.decode('utf-8')
					new_output = json.loads(b)
				except Exception as e:
					exception(f'{e}, {b=}')
					new_output = {
						'status': 'FAILED', 
						'error': f'{b},{e}'
					}
				if not new_output.get('status'):
					e = Exception(f"{new_output=} {upappid=}, {apiname=} has not status field")
					critical(f'{e}')
					raise e
				if lastoutout.get('status', '') != new_output.get('status'):
					llmusage.status = new_output['status']
					ns = {
						'id': llmusage.id,
						'status': llmusage.status
					}
					if 'usage' in new_output.keys():
						ns['usages'] = json.dumps(new_output['usage'])
					await append_new_llmoutput(llmusage.ioinfo, new_output)
					await modify_llmusage(ns)
				if  llmusage.status in ['UNKNOWN', 'FAILED', 'SUCCEEDED']:
					critical(f'finished .. {llmusage.status=}')
					return

				if onetime:
					critical(f'onetime is true, returned')
					return
				await asyncio.sleep(llm.query_period or 30)
				critical(f'{llm.query_period=} seconds will retry, {new_output["status"]=}')
	except asyncio.CancelledError:
		critical(f'query_task_status cancelled for {luid=}')
		raise
	except Exception as e:
		exception(f'query_task_status error for {luid=}: {e}')
		raise


async def async_uapi_request_product(llm, api_userid, user_id, user_org_id, params_kw, luid):
	"""Product interface version of async task submission. Returns dict with task info."""
	env = ServerEnv()
	from uapi.appapi import UAPI
	uapi = UAPI(llm.upappid, llm.apiname)
	b = None
	try:
		start_timestamp = time.time()
		if llm.callbackurl:
			params_kw.callbackurl = llm.callbackurl

		b = await uapi.call(llm.upappid, llm.apiname, api_userid, params=params_kw)
		if isinstance(b, bytes):
			b = b.decode('utf-8')
		debug(f'async task submitted: {b}')
		d = DictObject(**json.loads(b))

		responsed_seconds = time.time() - start_timestamp
		finish_seconds = responsed_seconds

		llmusage = DictObject()
		llmusage.id = luid
		llmusage.llmid = llm.id
		llmusage.use_date = curDateString()
		llmusage.use_time = timestampstr()
		llmusage.userid = user_id
		ioinfo = {"input": dict(params_kw), "output": [d]}
		webpath = await write_llmio(luid, ioinfo)
		llmusage.ioinfo = webpath
		llmusage.taskid = d.taskid
		llmusage.transno = params_kw.get('transno', luid)
		llmusage.responsed_seconds = responsed_seconds
		llmusage.finish_seconds = finish_seconds
		llmusage.status = d.status
		llmusage.userorgid = user_org_id
		llmusage.tenantid = params_kw.get('tenantid', params_kw.get('tentantid'))
		llmusage.ownerid = llm.ownerid
		llmusage.accounting_status = 'created'
		await write_llmusage(llmusage)

		if d.status == 'FAILED':
			return {
				'success': False,
				'message': f'Task submission failed: {d}',
				'task_id': luid,
				'status': 'FAILED',
			}

		# Task submitted successfully — return task info
		# Background polling is handled by existing query_task_status or callback
		return {
			'success': True,
			'result': {'taskid': d.taskid, 'status': d.status},
			'usage_data': {},
			'resource_ref_id': llm.id,
			'task_id': luid,
			'external_task_id': d.taskid,
			'status': d.status,
		}

	except Exception as e:
		exception(f'async_uapi_request_product error: {e}')
		return {
			'success': False,
			'message': str(e),
			'task_id': luid,
			'status': 'FAILED',
		}		
