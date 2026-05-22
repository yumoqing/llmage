import json
import time
import asyncio
import aiofiles
from random import randint
from functools import partial
from traceback import format_exc
from sqlor.dbpools import DBPools, get_sor_context
from appPublic.log import debug, exception, error, critical
from appPublic.uniqueID import getID
from appPublic.dictObject import DictObject
from appPublic.timeUtils import curDateString, timestampstr
from uapi.appapi import UAPI, sor_get_callerid, sor_get_uapi
from ahserver.serverenv import get_serverenv, ServerEnv
from ahserver.filestorage import FileStorage
from appPublic.jsonConfig import getConfig
from appPublic.streamhttpclient import StreamHttpClient

async def update_llmusage(ns):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		await sor.U('llmusage', ns)

async def get_user_tpac(userid):
	env = ServerEnv()
	config = getConfig()
	async with get_sor_context(env, 'rbac') as sor:
		recs = await sor.R('users', {'id': userid})
		if recs:
			tpac = config.tpacs.get(recs[0].sync_from)
			return tpac
	return None

async def get_tpac_balance(tpac, userid):
	url = tpac.get_user_balance_url
	hc = StreamHttpClient()
	try:
		b = await hc.request('GET', url, params={'userid': userid})
		if b:
			d = json.loads(b.decode('utf-8'))
			if d['status'] == 'ok':
				return d['balance']
		exception(f'{url=}, {userid=}, {b} error')
		return None
	except Exception as e:
		exception(f'{url=}, {userid=}, error:{e}')
		return None

async def tpac_accounting(tpac, userid, llmid, amount, usage, luid):
	url = tpac.accounting_url
	hc = StreamHttpClient()
	d = {
		'userid': userid,  
		'llmid': llmid, 
		'amount': amount, 
		'usage': usage
	}
	status = 'failed'
	try:
		b = await hc.request('POST', url, data=d)
		d = json.loads(b.decode('utf-8'))
		if d['status'] == 'ok':
			debug(f'{d=}'
			await update_llmusage({'id': luid, 'accounting_status': 'accounted'})
			return
		raise Exception(f'{d} tpac accounting error')
	except Exception as e:
		exception(f'{userid=}, {llmid=}, {amount=}, {usage=}  tpac accounting error:{e}')
		raise e

async def append_new_llmoutput(webpath, output):
	fs = FileStorage()
	p = fs.realPath(webpath)
	if isinstance(output, str):
		output = json.loads(output)
	bin = await read_webpath(webpath)
	io = json.loads(bin.decode('utf-8'))
	io['output'].append(output)
	async with aiofiles.open(p, 'wb') as f:
		iostr = json.dumps(io, ensure_ascii=False, indent=4)
		await f.write(iostr.encode('utf-8'))
	
async def get_lastoutput(webpath):
	bin =  await read_webpath(webpath)
	io = json.loads(bin.decode('utf-8'))
	return io['output'][-1]

async def read_webpath(webpath):
	fs = FileStorage()
	p = fs.realPath(webpath)
	async with aiofiles.open(p,'rb') as f:
		bin = await f.read()
		return bin

async def write_llmio(luid, io_dic):
	fs = FileStorage()
	s = io_dic
	if not isinstance(io_dic, str):
		s = json.dumps(io_dic, ensure_ascii=False, indent=4)
	name = f'{luid}.json'
	webpath = await fs.save(name, s, userid='llmio')
	return webpath

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

async def get_llms_by_catelog_to_customer(catelogid=None, orderby='providerid'):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		today = curDateString()
		# Join with llm_api_map to get catalog relationship
		sql = """select distinct a.*, b.name as catelogname, m.llmcatelogid as catelog_id 
			from llm a 
			join llm_api_map m on a.id = m.llmid 
			join llmcatelog b on m.llmcatelogid = b.id
			where a.enabled_date <= ${today}$
			and a.ppid is not null
			and a.expired_date > ${today}$
			"""
		sortstr='catelog_id, ' + orderby
		params = {'today': today, 'sort': sortstr}
		if catelogid:
			sql += " and m.llmcatelogid = ${catelogid}$"
			params['catelogid'] = catelogid
			
		debug(f'{sql=}')
		recs = await sor.sqlExe(sql, params.copy())
		debug(f'{sql=}, {recs=}, {params=}')
		d = []
		cid = ''
		x = None
		for r in recs:
			if cid != r.catelog_id:
				x = {
					'catelogid': r.catelog_id,
					'catelogname': r.catelogname,
					'llms': [r]
				}
				d.append(x)
				cid = r.catelog_id
			else:
				x['llms'].append(r)
		return d
	return []

async def get_llms_by_catelog(catelogid=None, orderby='providerid'):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		today = curDateString()
		# Join with llm_api_map to get catalog relationship
		sql = """select distinct a.*, b.name as catelogname, m.llmcatelogid as catelog_id 
			from llm a 
			join llm_api_map m on a.id = m.llmid 
			join llmcatelog b on m.llmcatelogid = b.id
			where a.enabled_date <= ${today}$
			and a.expired_date > ${today}$"""
		params = {'today': today, 'sort': orderby}
		if catelogid:
			sql += " and m.llmcatelogid = ${catelogid}$"
			params['catelogid'] = catelogid
			
		sql += " order by m.llmcatelogid, a.id"
		
		recs = await sor.sqlExe(sql, params)
		d = []
		cid = ''
		x = None
		for r in recs:
			if cid != r.catelog_id:
				x = {
					'catelogid': r.catelog_id,
					'catelogname': r.catelogname,
					'llms': [r]
				}
				d.append(x)
				cid = r.catelog_id
			else:
				x['llms'].append(r)
		return d
	return []
	
async def get_llm(llmid, catelogid=None):
	today = curDateString()
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		sql = """select a.id,
a.name,
a.model,
a.providerid,
a.description,
a.iconid,
a.upappid,
a.ownerid,
a.min_balance,
m.llmcatelogid,
m.apiname,
m.query_apiname,
m.query_period,
m.ppid,
e.ioid, 
e.stream, 
e.callbackurl, 
f.input_fields,
lc.name as catelogname
from llm a
,llm_api_map m
,llmcatelog lc
,upapp c
,uapi e
,uapiio f
where a.id = m.llmid
and a.upappid = c.id
and c.id = e.upappid 
and m.apiname = e.name
and e.ioid = f.id
and a.id = ${llmid}$
and a.expired_date > ${today}$
and a.enabled_date <= ${today}$
"""
		ns = {'llmid': llmid, 'today': today}
		if catelogid:
			sql += ' and m.llmcatelogid = ${catelogid}$ '
			ns['catelogid'] = catelogid
		else:
			sql += " and m.isdefaultcatelog = '1'"
		recs = await sor.sqlExe(sql, ns.copy())
		if len(recs) > 0:
			r = recs[0]
			return r
		else:
			debug(f'{llmid=} not found, {ns=}, {sql=}')
			return None
	exception(f'Error: {format_exc()}')
	return None


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

