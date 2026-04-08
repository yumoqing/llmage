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
from uapi.appapi import UAPI, sor_get_callerid, sor_get_uapi
from ahserver.serverenv import get_serverenv, ServerEnv
from ahserver.filestorage import FileStorage

async def llm_query_orders(userorgid, page, pagerows=80):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		sql = """select a.llmid,
a.use_date,
a.use_time,
a.userid,
a.usages,
a.status,
a.amount,
a.userorgid,
a.accounting_status,
b.name,
b.model
from llmusage a, llm b
where userorgid = ${userorgid}$
	and a.llmid = b.id
"""
		ns = dict(
			page=page,
			pagerows=pagerows,
			sort="use_time desc",
			userorgid=userorgid)

		data = await sor.sqlExe(sql, ns)
		return data
	return {'total': 0, 'rows':[]}

async def get_llm_by_model(id, lctype=None):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		sql = 'select * from llm where model=${model}$'
		recs = await sor.R('llm', {'model': model})
		return recs

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
	
class BufferedLLMs:
	llms = {}
	async def get_llm(self, llmid):
		today = curDateString()
		k = f'{llmid}.{today}'
		d = BufferedLLMs.llms.get(k)
		if d:
			return d
		env = ServerEnv()
		async with get_sor_context(env, 'llmage') as sor:
			sql = """select x.*,
	z.input_fields
	from (
	select a.*, e.ioid, e.callbackurl, e.stream, f.input_fields as inputfields
	from llm a, upapp c, uapiset d, uapi e, uapiio f
	where a.upappid = c.id
		and c.apisetid = d.id
		and e.apisetid = d.id
		and e.ioid = f.id
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
				dates = BufferedLLMs.llms.get(llmid, [])
				dates.append(today)
				cnt = len(dates)
				if cnt > 2:
					for i in range(0, cnt -2):
						dat = dates[i]
						del BufferedLLMs.llms[f'{llmid}.{dat}']
					dates = dates[-2:]
					BufferedLLMs.llms[llmid] = dates
				BufferedLLMs.llms[k] = r
				return r
			else:
				debug(f'{llmid=} not found, {ns=}, {sql=}')
				return None
		exception(f'Error: {format_exc()}')
		return None

async def get_llm(llmid):
	bllms = BufferedLLMs()
	return await bllms.get_llm(llmid)

async def get_owner_userid(llm):
	env = ServerEnv()
	userid = await env.uapi_data.get_calluserid(llm.upappid, orgid=llm.ownerid)
	return userid

async def write_llmusage(llmusage):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		await sor.C('llmusage', llmusage)

async def llm_query_price(llmid, config_data):
	env = ServerEnv()
	llm = await get_llm(llmid)
	if llm.ppid is None:	
		e = Exception(f'{llm=} ppid is None')
		exception(f'{e}')
		raise e
	prices = await env.buffered_charging(llm.ppid, config_data)
	return prices

