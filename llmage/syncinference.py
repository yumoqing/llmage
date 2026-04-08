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
# from uapi.appapi import UAPI, sor_get_callerid, sor_get_uapi
from ahserver.serverenv import get_serverenv, ServerEnv
from ahserver.filestorage import FileStorage
from .accounting import llm_accounting, llm_charging
from .utils import *

async def sync_uapi_request(request, llm, callerid, callerorgid, params_kw=None):
	env = request._run_ns.copy()
	if not params_kw:
		params_kw = env.params_kw
	# callerid = await env.get_user()
	# callerorgid = await env.get_userorgid()
	# uapi = UAPI(request, sor=sor)
	uapi = UpAppApi()
	userid = await get_owner_userid(llm)
	outlines = []
	b = None
	d = None
	luid = getID()
	try:
		start_timestamp = time.time()
		responsed_seconds = None
		finish_seconds = None
		b = await uapi.call(llm.upappid, llm.apiname, userid, params=params_kw)
		if isinstance(b, bytes):
			b = b.decode('utf-8')
		d = json.loads(b)
		status = d.get('status')
		usage = d.get('usage')
		if status and status != 'SUCCEEDED':
			raise Exception(d['error'])
		responsed_seconds = time.time() - start_timestamp
		finish_seconds = responsed_seconds
		llmusage = DictObject()
		llmusage.id = luid
		llmusage.llmid = llm.id
		llmusage.use_date = curDateString()
		llmusage.use_time = timestampstr()
		llmusage.userid = callerid
		llmusage.usages = json.dumps(usage, ensure_ascii=False)
		llmusage.ioinfo = json.dumps({
			"input": params_kw,
			"output": [d]
		}, ensure_ascii=False)
		llmusage.transno = params_kw.transno
		llmusage.responsed_seconds = responsed_seconds
		llmusage.finish_seconds = finish_seconds
		llmusage.status = 'SUCCEEDED'
		llmusage.amount = llmusage.cost = 0.00
		""" 联机不记账
		if llm.ppid:
			try:
				charging = await llm_charging(llm.ppid, llmusage)
				if charging:
					llmusage.amount = charging.amount
					llmusage.cost = charging.cost
				else:
					llmusage.amount = llmusage.cost = 0.0
			except Exception as e:
				e = Exception(f'{llm.pid} charging error{e}')
				exception(f'{e}')
		else:
			llmusage.amount = 0
			llmusage.cost = 0
		"""
		llmusage.userorgid = callerorgid
		llmusage.ownerid = llm.orgid
		llmusage.accounting_status = 'created'
		b = json.dumps(d, ensure_ascii=False)
		yield b
		await write_llmusage(llmusage)
		"""联机不记账
		if llmusage.amount > 0.0001:
			await llm_accounting(llmusage)
		"""
	except Exception as e:
		exception(f'{e=},{format_exc()}')
		estr = erase_apikey(e)
		ed = {"error": f"ERROR:{estr}", "status": "FAILED" ,"llmusageid": luid}
		s = json.dumps(ed, ensure_ascii=False)
		s = ''.join(s.split('\n'))
		outlines.append(ed)
		yield f'{s}\n'

