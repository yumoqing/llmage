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

def erase_apikey(e):
	e = str(e)
	ss = e.split('Bearer ')
	if len(ss) < 2:
		return e

	for i, c in enumerate(ss[1]):
		if c in ['"', "'"]:
			newb = "XXXXXXXX" + ss[1][i:]
			break
	return ss[0] + 'Bearer ' + newb

async def get_llmproviders():
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		sql = """select a.providerid, a.iconid, b.orgname 
from llm a, organization b
where a.providerid = b.id
group by a.providerid, a.iconid, b.orgname"""
		return await sor.sqlExe(sql, {})
	return []

async def get_llms_sort_by_provider():
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		today = curDateString()		 
		sql = """select a.*, b.orgname from llm a, organization b
where a.enabled_date <= ${today}$
	and a.expired_date > ${today}$
	and a.providerid = b.id
	order by a.providerid, a.id
	"""									 
		recs = await sor.sqlExe(sql, {'today': today})
		d = []
		x = None
		oldpid = '-111'
		for l in recs:
			if l.providerid != oldpid:
				x = {
					'id': l.providerid,
					'orgname': l.orgname,
					'llms': [l]
				}
				d.append(x)
				oldpid = l.providerid
			else:
				x['llms'].append(l)
		return d
	return []

async def get_llmcatelogs():
	db = DBPools()
	dbname = get_serverenv('get_module_dbname')('llmage')
	async with db.sqlorContext(dbname) as sor:
		recs = await sor.R('llmcatelog', {})
		return recs

	return []

async def get_llms_by_catelog():
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		today = curDateString()
		sql = """select a.*, b.name as catelogname from llm a, llmcatelog b
where a.llmcatelogid = b.id
	and enabled_date <= ${today}$
	and expired_date > ${today}$
	order by a.llmcatelogid, a.id
	"""
		recs = await sor.sqlExe(sql, {'today': today})
		d = []
		cid = ''
		x = None
		for r in recs:
			if cid != r.llmcatelogid:
				x = {
					'catelogid': r.llmcatelogid,
					'catelogname': r.catelogname,
					'llms': [r]
				}
				d.append(x)
				cid = r.llmcatelogid
			else:
				x['llms'].append(r)
		return d
	return []
	
async def get_llm(llmid):
	db = DBPools()
	dbname = get_serverenv('get_module_dbname')('llmage')
	async with db.sqlorContext(dbname) as sor:
		today = curDateString()
		sql = """select x.*,
z.input_fields
from (
select a.*, e.ioid, e.callbackurl, e.stream
from llm a, upapp c, uapiset d, uapi e
where a.upappid = c.id
	and c.apisetid = d.id
	and e.apisetid = d.id
	and a.apiname = e.name
	and a.expired_date > ${today}$
	and a.enabled_date <= ${today}$
) x left join uapiio z on x.ioid = z.id
where x.id = ${llmid}$	
"""
		ns = {'llmid': llmid, 'today': today}
		recs = await sor.sqlExe(sql, ns.copy())
		if len(recs) > 0:
			r = recs[0]
			api = await sor_get_uapi(sor, r.upappid, r.apiname)
			if api is None:
				e = Exception(f'{r.upappid=},{r.apiname=} uapi not found')
				exception(f'{e=}\n{format_exc()}')
				raise e
			r.inputfields = api.input_fields
			return recs[0]
		else:
			debug(f'{llmid=} not found, {ns=}, {sql=}')
			return None
	exception(f'{db.e_except}\n{format_exc()}')
	return None

async def get_owner_userid(sor, llm):
	sql = '''select a.ownerid as userid from upappkey a, upapp b
where a.upappid=b.id
	and a.orgid = b.ownerid
	and a.orgid = ${ownerid}$'''
	recs = await sor.sqlExe(sql, {'ownerid': llm.ownerid})
	i = randint(0, len(recs)-1)
	return recs[i].userid

async def write_llmusage(llmusage):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		await sor.C('llmusage', d)

