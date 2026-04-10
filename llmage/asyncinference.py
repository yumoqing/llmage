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
from appPublic.timeUtils import curDateString, timestampstr
from appPublic.base64_to_file import base64_to_file, getFilenameFromBase64
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

async def get_asynctask_status(request, taskid):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		recs = await sor.R('llmusage', {'taskid': taskid})
		if recs:
			r = recs[0]
			if r.status not in ['SUCCEEDED', 'FAILED']:
				await query_task_status(request, r.id, onetime=True)
				recs = await sor.R('llmusage', {'id': r.id})
				r = recs[0]
			output = await get_lastoutput(r.ioinfo)
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
			yield f'{ed}\n'
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
		llmusage.ownerid = llm.orgid
		llmusage.accounting_status = 'created'
		b = json.dumps(d, ensure_ascii=False)
		yield b
		await write_llmusage(llmusage)
		# if llm.callbackurl:
		#	return
		if d.status == 'FAILED':
			e = Exception(f'resp={d} FFAILED')
			return
		asyncio.create_task(query_task_status(request,  luid))

	except Exception as e:
		ed = {"error": f"ERROR:{e}", "status": "FAILED"}
		s = json.dumps(ed, ensure_ascii=False)
		s = ''.join(s.split('\n'))
		exception(s)
		yield f'{s}\n'
		return

async def modify_llmusage_status(llmusage):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		await sor.U('llmusage', {
			'id': llmusage.id,
			'status': llmusage.status
		})

async def get_llm_llmusage(luid):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		recs = await sor.R('llmusage', {'id': luid})
		if len(recs) == 0:
			e = Exception(f'{luid=} is not found in llmusage')
			exception(f'{e}')
			raise e
		llmusage = recs[0]
		if llmusage.status == 'SUCCEEDED':
			return
		if llmusage.status == 'FAILED':
			return
		llms = await sor.R('llm', {'id': llmusage.llmid})
		if len(llms) == 0:
			e = Exception(f'{llmusage.llmid=} not found in llm')
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

	for apiname in apinames:
		while True:
			lastoutout = await get_lastoutput(llmusage.ioinfo)
			if lastoutout['status'] in ['FAILED', 'SUCCEEDED']:
				critical(f"{lastoutout['status']=}")
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
			if lastoutout['status'] != new_output['status']:
				llmusage.status = new_output['status']
				await append_new_llmoutput(llmusage.id, new_output)
				await modify_llmusage_status(llmusage)
			if  llmusage.status in ['FAILED', 'SUCCEEDED']:
				dcritical(f'finished .. {llmusage.status=}')
				return

			if onetime:
				critical(f'onetime is true, returned')
			await asyncio.sleep(llm.query_period or 30)
			critical(f'{llm.query_period=} seconds will retry, {changed.status=}')
					
