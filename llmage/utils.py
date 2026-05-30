import json
import asyncio
import aiofiles
from random import randint
from functools import partial
from traceback import format_exc
import time
from sqlor.dbpools import DBPools, get_sor_context
from appPublic.log import debug, exception, error, critical
from appPublic.uniqueID import getID
from appPublic.dictObject import DictObject
from appPublic.timeUtils import curDateString, timestampstr
from uapi.appapi import UAPI, sor_get_callerid, sor_get_uapi, get_uapi
from ahserver.serverenv import get_serverenv, ServerEnv
from ahserver.filestorage import FileStorage
from appPublic.jsonConfig import getConfig
from appPublic.streamhttpclient import StreamHttpClient

# =============================================================
# Process-level cache for uapi/uapiio (static config, rarely changes)
# =============================================================
_UAPI_CACHE_TTL = 300  # 5 minutes
_uapi_cache = {}       # key: "upappid:apiname" -> {data, ts}
_uapiio_cache = {}     # key: "ioid" -> {data, ts}


async def _get_uapi_cached(upappid, apiname):
    """Get uapi record with process-level cache (uapi config rarely changes)"""
    global _uapi_cache
    cache_key = f"{upappid}:{apiname}"
    cached = _uapi_cache.get(cache_key)
    if cached and (time.time() - cached['ts']) < _UAPI_CACHE_TTL:
        return cached['data']
    uapi_rec = await get_uapi(upappid, apiname)
    _uapi_cache[cache_key] = {'data': uapi_rec, 'ts': time.time()}
    return uapi_rec


async def _get_uapiio_cached(ioid):
    """Get uapiio record with process-level cache (io config rarely changes)"""
    global _uapiio_cache
    if ioid is None:
        return None
    cached = _uapiio_cache.get(ioid)
    if cached and (time.time() - cached['ts']) < _UAPI_CACHE_TTL:
        return cached['data']
    env = ServerEnv()
    uapi_dbname = get_serverenv('get_module_dbname')('uapi')
    async with DBPools().sqlorContext(uapi_dbname) as sor:
        recs = await sor.R('uapiio', {'id': ioid})
        result = recs[0] if recs else None
    _uapiio_cache[ioid] = {'data': result, 'ts': time.time()}
    return result


def invalidate_uapi_cache(upappid=None, apiname=None):
    """Invalidate uapi/uapiio cache entries. Call when uapi config changes."""
    global _uapi_cache, _uapiio_cache
    if upappid and apiname:
        _uapi_cache.pop(f"{upappid}:{apiname}", None)
    else:
        _uapi_cache.clear()
        _uapiio_cache.clear()


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
	url = tpac.get_tpac_balance_url
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
	url = tpac.tpac_accounting_url
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
			debug(f'{d=}')
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
	and a.status = 'published'
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
	and a.status = 'published'
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

async def get_llmage_llm(llmid=None, catelogid=None):
	"""Unified accessor for llm + llm_api_map + llmcatelog.
	For non-API-call scenarios only (display, listing, querying, accounting).
	Do NOT use for vendor model API calls — use get_llm() instead.
	
	- llmid: get specific llm by id (returns single DictObject or None)
	- catelogid: filter by catalog (returns list)
	- neither: return all with catalog info (returns list)
	"""
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		sql = """select a.id, a.name, a.model, a.providerid, a.description,
a.iconid, a.upappid, a.ownerid, a.min_balance, a.status,
m.llmcatelogid, m.apiname, m.query_apiname, m.query_period, m.ppid, m.isdefaultcatelog,
lc.name as catelogname
from llm a
join llm_api_map m on a.id = m.llmid
join llmcatelog lc on m.llmcatelogid = lc.id
where 1=1
"""
		ns = {}
		if llmid:
			sql += " and a.id = ${llmid}$ and m.isdefaultcatelog = '1'"
			ns['llmid'] = llmid
		if catelogid:
			sql += " and m.llmcatelogid = ${catelogid}$"
			ns['catelogid'] = catelogid
		sql += " order by m.llmcatelogid, a.id"
		recs = await sor.sqlExe(sql, ns)
		if llmid:
			return recs[0] if recs else None
		return recs

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
		sql = """select distinct a.*, 
b.name as catelogname, 
m.llmcatelogid as catelog_id,
m.apiname,
m.query_apiname,
m.query_period,
m.ppid
			from llm a 
			join llm_api_map m on a.id = m.llmid 
			join llmcatelog b on m.llmcatelogid = b.id
			where a.enabled_date <= ${today}$
			and a.status = 'published'
			and m.ppid is not null
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
			and a.status = 'published'
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
    """Get LLM with full uapi info for vendor API calls.
    Refactored to use get_llmage_llm() + cached uapi/uapiio lookups
    instead of a 6-table JOIN.

    Returns DictObject with merged fields:
      From get_llmage_llm: id, name, model, providerid, description,
        iconid, upappid, ownerid, min_balance, status, llmcatelogid,
        apiname, query_apiname, query_period, ppid, isdefaultcatelog,
        catelogname
      From uapi (cached):  ioid, stream, callbackurl
      From uapiio (cached): input_fields
    """
    # Step 1: Get base info from get_llmage_llm (3-table JOIN: llm + llm_api_map + llmcatelog)
    llm = await get_llmage_llm(llmid, catelogid)
    if not llm:
        debug(f'{llmid=} not found via get_llmage_llm')
        return None

    # Step 2: Get uapi info (cached, keyed by upappid:apiname)
    uapi = await _get_uapi_cached(llm.upappid, llm.apiname)
    if not uapi:
        debug(f'uapi not found: upappid={llm.upappid}, apiname={llm.apiname}')
        return None

    # Step 3: Get uapiio info (cached, keyed by ioid)
    uapiio = await _get_uapiio_cached(uapi.ioid)

    # Merge uapi fields into llm result
    llm.ioid = uapi.ioid
    llm.stream = uapi.stream
    llm.callbackurl = uapi.callbackurl
    llm.input_fields = uapiio.input_fields if uapiio else '{}'

    return llm


async def write_llmusage(llmusage):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		await sor.C('llmusage', llmusage)

async def llm_query_price(llmid, config_data):
	env = ServerEnv()
	llm = await get_llmage_llm(llmid)
	if llm.ppid is None:	
		e = Exception(f'{llm=} ppid is None')
		exception(f'{e}')
		raise e
	prices = await env.buffered_charging(llm.ppid, config_data)
	return prices

