import json
import time
import asyncio
from random import randint
from functools import partial
from traceback import format_exc
from sqlor.dbpools import DBPools, get_sor_context
from appPublic.log import debug, exception
from appPublic.uniqueID import getID
from appPublic.dictObject import DictObject
from appPublic.timeUtils import curDateString, timestampstr
from appPublic.base64_to_file import base64_to_file, getFilenameFromBase64
from uapi.appapi import UAPI, sor_get_callerid, sor_get_uapi
from ahserver.serverenv import get_serverenv, ServerEnv
from ahserver.filestorage import FileStorage
from llmage.accounting import llm_accounting

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

async def get_llms_by_provider(pid):
	env = ServerEnv()
    async with get_sor_context(env, 'llmage') as sor:
		today = curDateString()         
        sql = """select * from llm  
where providerid = ${pid}$
    and enabled_date <= ${today}$       
    and expired_date > ${today}$            
    """                                     
        recs = await sor.sqlExe(sql, {'pid': pid, 'today': today})
        return recs                             
    return []

async def get_llmcatelogs():
	db = DBPools()
	dbname = get_serverenv('get_module_dbname')('llmage')
	async with db.sqlorContext(dbname) as sor:
		recs = await sor.R('llmcatelog', {})
		return recs

	return []

async def get_llms_by_catelog(catelogid):
	debug(f'{catelogid=}')
	db = DBPools()
	dbname = get_serverenv('get_module_dbname')('llmage')
	async with db.sqlorContext(dbname) as sor:
		today = curDateString()
		sql = """select * from llm 
where llmcatelogid = ${llmcatelogid}$
	and enabled_date <= ${today}$
	and expired_date > ${today}$
	"""
		recs = await sor.sqlExe(sql, {'llmcatelogid': catelogid, 'today': today})
		return recs
	return []
	
async def get_llm(llmid):
	db = DBPools()
	dbname = get_serverenv('get_module_dbname')('llmage')
	async with db.sqlorContext(dbname) as sor:
		today = curDateString()
		sql = """select x.*,
z.input_fields,
y.system_message, 
y.user_message,
y.assisant_message 
from (
select a.*, b.hfid, e.ioid, e.stream
from llm a, llmcatelog b,upapp c, uapiset d, uapi e
where a.llmcatelogid = b.id
    and a.upappid = c.id
    and c.apisetid = d.id
    and e.apisetid = d.id
    and a.apiname = e.name
	and a.expired_date > ${today}$
	and a.enabled_date <= ${today}$
) x left join historyformat y on x.hfid = y.id
	left join uapiio z on x.ioid = z.id
where x.id = ${llmid}$	
"""
		recs = await sor.sqlExe(sql, {'llmid': llmid, 'today': today})
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
			debug(f'{llmid=} not found')
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

async def write_llmusage(id, llm, userid, usage, params_kw, outdata, sor):
	debug(f'{params_kw=}, {outdata=}')
	d = {
		"id": id,
		"llmid": llm.id,
		"use_date": curDateString(),
		"use_time": timestampstr(),
		"userid": userid,
		"transno": params_kw.transno,
		"evalvalue": 0,
		"usages": json.dumps(usage),
		"ioinfo": json.dumps({
			"input": params_kw,
			"output": outdata
		}, ensure_ascii=False)
	}
	await sor.C('llmusage', d)

async def uapi_request(request, llm, sor, params_kw=None):
	env = request._run_ns.copy()
	if not params_kw:
		params_kw = env.params_kw
	callerorgid = await env.get_userorgid()
	callerid = await env.get_user()
	uapi = UAPI(request, sor=sor)
	userid = await get_owner_userid(sor, llm)
	outlines = []
	txt = ''
	luid = getID()
	try:
		t1 = time.time()
		t2 = t1
		t3 = t1
		first = True
		async for l in uapi.stream_linify(llm.upappid, llm.apiname, userid, 
					params=params_kw):
			if first:
				first = False
				t2 = time.time() 
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
				d['llmusageid'] = luid
				outlines.append(d)
				yield json.dumps(d) + '\n'
		usage = outlines[-1].get('usage',{})
		t3 = time.time()
		usage['response_time'] = t2 - t1
		usage['finish_time'] = t3 - t1
		if not usage.get('completion_tokens'):
			usage['completion_tokens'] = len(txt)
		if not usage.get('prompt_tokens'):
			cnt = 0
			if params_kw.prompt:
				cnt += len(params_kw.prompt)
			if params_kw.negitive_prompt:
				cnt += len(params_kw.negitive_promot)
			usage['prompt_tokens'] = cnt
		u = await write_llmusage(luid, llm, callerid, usage, params_kw, outlines, sor)
		if llm.ppid and callerorgid != llm.ownerid:
			debug(f'{usage=},{llm.ownerid=},{callerorgid=}')
			await llm_accounting(request, llm.id, usage, callerorgid, callerid)
	except Exception as e:
		exception(f'{e=},{format_exc()}')
		estr = erase_apikey(e)
		ed = {"error": f"ERROR:{estr}:{format_exc()}", "status": "FAILED" ,"llmusageid": luid}
		s = json.dumps(ed)
		s = ''.join(s.split('\n'))
		outlines.append(ed)
		yield f'{s}\n'
		await write_llmusage(luid, llm, callerid, None, params_kw, outlines, sor)
		return

async def sync_uapi_request(request, llm, sor, params_kw=None):
	env = request._run_ns.copy()
	if not params_kw:
		params_kw = env.params_kw
	callerid = await env.get_user()
	callerorgid = await env.get_userorgid()
	uapi = UAPI(request, sor=sor)
	userid = await get_owner_userid(sor, llm)
	outlines = []
	b = None
	d = None
	t1 = t2 = t3 = time.time()
	luid = getID()
	try:
		
		b = await uapi.call(llm.upappid, llm.apiname, userid, params=params_kw)
		if isinstance(b, bytes):
			b = b.decode('utf-8')
		d = json.loads(b)
	except Exception as e:
		exception(f'{e=},{format_exc()}')
		estr = erase_apikey(e)
		ed = {"error": f"ERROR:{estr}:{format_exc()}", "status": "FAILED" ,"llmusageid": luid}
		s = json.dumps(ed)
		s = ''.join(s.split('\n'))
		outlines.append(ed)
		yield f'{s}\n'
		await write_llmusage(luid, llm, callerid, None, params_kw, outlines, sor)
		return
	d['llmusageid'] = luid
	outlines.append(d)
	t2 = t3 = time.time()
	usage = d.get('usage', {})
	usage['response_time'] = t2 - t1
	usage['finish_time'] = t3 - t1
	b = json.dumps(d, ensure_ascii=False)
	yield b
	await write_llmusage(luid, llm, callerid, usage, params_kw, outlines, sor)
	if llm.ppid and callerorgid != llm.ownerid:
		debug(f'{usage=},{llm.ownerid=},{callerorgid=}')
		await llm_accounting(request, llm.id, usage, callerorgid, callerid)

async def async_uapi_request(request, llm, sor, params_kw=None):
	env = request._run_ns.copy()
	if not params_kw:
		params_kw = env.params_kw
	callerorgid = await env.get_userorgid()
	callerid = await env.get_user()
	uapi = UAPI(request, sor=sor)
	userid = await get_owner_userid(sor, llm)
	outlines = []
	b = None
	t1 = t2 = t3 = time.time()
	luid = getID()
	try:
		b = await uapi.call(llm.upappid, llm.apiname, userid, params=params_kw)
	except Exception as e:
		exception(f'{e=},{format_exc()}')
		estr = erase_apikey(e)
		ed = {"error": f"ERROR:{estr}:{format_exc()}", "status": "FAILED" ,"llmusageid": luid}
		s = json.dumps(ed)
		s = ''.join(s.split('\n'))
		outlines.append(ed)
		yield f'{s}\n'
		await write_llmusage(luid, llm, callerid, None, params_kw, outlines, sor)
		return
	if isinstance(b, bytes):
		b = b.decode('utf-8')
	debug(f'task sumbited:{b}')
	d = DictObject(**json.loads(b))
	outlines.append(d)
	t2 = time.time()
	uapi = UAPI(request, sor=sor)
	apinames = [ name.strip() for name in llm.query_apiname.split(',') ]
	for apiname in apinames:
		while True:
			b = None
			try:
				b = await uapi.call(llm.upappid, apiname, userid, params=d)
			except Exception as e:
				exception(f'{e=},{format_exc()}')
				estr = erase_apikey(e)
				ed = {"error": f"ERROR:{estr}:{format_exc()}", "status": "FAILED" ,"llmusageid": luid}
				s = json.dumps(ed)
				s = ''.join(s.split('\n'))
				outlines.append(ed)
				yield f'{s}\n'
				await write_llmusage(luid, llm, callerid, None, params_kw, outlines, sor)
				return

			if isinstance(b, bytes):
				b = b.decode('utf-8')
			d = json.loads(b)
			rzt = DictObject(**json.loads(b))
			rzt['llmusageid'] = luid
			b = json.dumps(rzt, ensure_ascii=False)
			b = ''.join(b.split('\n'))
			debug(f'response line = {b}')
			yield b + '\n'
			if not rzt.status or rzt.status == 'FAILED':
				debug(f'{b=} return error')
				outlines.append(rzt)
				await write_llmusage(luid, llm, callerid, None, params_kw, outlines, sor)
				return
			if rzt.status == 'SUCCEEDED':
				await asyncio.sleep(1)
				outlines.append(rzt)
				usage = rzt.get('usage', {})
				t3 = time.time()
				usage['response_time'] = t2 - t1
				usage['finish_time'] = t3 -t1
				await write_llmusage(luid, llm, callerid, usage, params_kw, outlines, sor)
				if llm.ppid and callerorgid != llm.ownerid:
					debug(f'{usage=},{llm.ownerid=},{callerorgid=}')
					await llm_accounting(request, llm.id, usage, callerorgid, callerid)
				
				d = rzt
				break
			period = llm.query_period or 30
			await asyncio.sleep(period)

def b64media2url(request, mediafile):
	env = request._run_ns
	entire_url = env.entire_url
	if mediafile.startswith('data:'):
		try:
			fs = FileStorage()
			fname = getFilenameFromBase64(mediafile)
			fpath = fs._name2path(fname)
			base64_to_file(mediafile, fpath)
			path = fs.webpath(fpath)
			return entire_url('/idfile?path=') + env.quote(path)
		except Exception as e:
			exception(f'{e}\n{format_exc()}')
			return ' '
	if mediafile.startswith('http://') or mediafile.startswith('https://'):
		return mediafile
	url = entire_url('/idfile?path=') + env.quote(mediafile)
	return url

async def inference(request, *args, params_kw=None, **kw):
	env = request._run_ns.copy()
	if not params_kw:
		params_kw = env.params_kw
	if not params_kw.transno:
		params_kw.transno = getID()
	llmid = params_kw.llmid
	dbname = env.get_module_dbname('llmage')
	db = env.DBPools()
	async with db.sqlorContext(dbname) as sor:
		llm = await get_llm(llmid)
		if llm.stream == 'async':
			f = partial(async_uapi_request, request, llm, sor, params_kw=params_kw)
			return await env.stream_response(request, f)
		if llm.stream == 'sync':
			f = partial(sync_uapi_request, request, llm, sor, params_kw=params_kw)
			return await env.stream_response(request, f)
		# env.update(llm)
		uapi = UAPI(request, sor=sor)
		f = partial(uapi_request, request, llm, sor, params_kw=params_kw)
		return await env.stream_response(request, f)
