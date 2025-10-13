import json
import asyncio
from random import randint
from functools import partial
from traceback import format_exc
from sqlor.dbpools import DBPools
from appPublic.log import debug, exception
from appPublic.uniqueID import getID
from appPublic.dictObject import DictObject
from appPublic.timeUtils import curDateString
from appPublic.base64_to_file import base64_to_file, getFilenameFromBase64
from uapi.appapi import UAPI, sor_get_callerid, sor_get_uapi
from ahserver.serverenv import get_serverenv
from ahserver.filestorage import FileStorage

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

async def uapi_request(request, llm, sor):
	env = request._run_ns.copy()
	caller_orgid = await env.get_userorgid()
	callerid = await env.get_user()
	uapi = UAPI(request, sor=sor)
	userid = await get_owner_userid(sor, llm)
	txt = ''
	try:
		async for l in uapi.stream_linify(llm.upappid, llm.apiname, userid, 
					params=env.params_kw):
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
				yield json.dumps(d) + '\n'
	except Exception as e:
		exception(f'{e=},{format_exc()}')
		yield f'{{"error": "ERROR:{e=}"}}\n'
		return

	debug(f'{txt=}')
	
async def sync_uapi_request(request, llm, sor):
	env = request._run_ns.copy()
	caller_orgid = await env.get_userorgid()
	callerid = await env.get_user()
	uapi = UAPI(request, sor=sor)
	userid = await get_owner_userid(sor, llm)
	b = None
	try:
		b = await uapi.call(llm.upappid, llm.apiname, userid, params=env.params_kw)
	except Exception as e:
		exception(f'{e=},{format_exc()}')
		yield f'{{"error": "ERROR:{e=}"}}\n'
		return
	if isinstance(b, bytes):
		b = b.decode('utf-8')
	debug(f'finished:{b}')
	yield b

async def async_uapi_request(request, llm, sor):
	env = request._run_ns.copy()
	caller_orgid = await env.get_userorgid()
	callerid = await env.get_user()
	uapi = UAPI(request, sor=sor)
	userid = await get_owner_userid(sor, llm)
	b = None
	try:
		b = await uapi.call(llm.upappid, llm.apiname, userid, params=env.params_kw)
	except Exception as e:
		exception(f'{e=},{format_exc()}')
		yield f'{{"error": "ERROR:{e=}"}}\n'
		return
	if isinstance(b, bytes):
		b = b.decode('utf-8')
	debug(f'task sumbited:{b}')
	d = DictObject(**json.loads(b))
	if not d.get('context'):
		debug(f'{b} error')
		yield '{"error":"server return no taskid"}\n'
		return
	uapi = UAPI(request, sor=sor)
	apinames = [ name.strip() for name in llm.query_apiname.split(',') ]
	for apiname in apinames:
		while True:
			b = None
			try:
				b = await uapi.call(llm.upappid, apiname, userid, params=d.context)
			except Exception as e:
				exception(f'{e=},{format_exc()}')
				yield f'{{"error": "ERROR:{e=}"}}\n'
				break

			if isinstance(b, bytes):
				b = b.decode('utf-8')
			b = ''.join(b.split('\n'))
			debug(f'response line = {b}')
			rzt = DictObject(**json.loads(b))
			yield b + '\n'
			if not rzt.status or rzt.status == 'FAILED':
				debug(f'{b=} return error')
				yield f'{{"error": "ERROR:{e=}"}}\n'
				return
			if rzt.status == 'SUCCEEDED':
				debug(f'{b=} return successed')
				await asyncio.sleep(1)
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

async def inference(request, *args, **kw):
	env = request._run_ns.copy()
	llmid = env.params_kw.llmid
	dbname = env.get_module_dbname('llmage')
	db = env.DBPools()
	async with db.sqlorContext(dbname) as sor:
		llm = await get_llm(llmid)
		if llm.stream == 'async':
			f = partial(async_uapi_request, request, llm, sor)
			return await env.stream_response(request, f)
		if llm.stream == 'sync':
			f = partial(sync_uapi_request, request, llm, sor)
			return await env.stream_response(request, f)
		# env.update(llm)
		uapi = UAPI(request, sor=sor)
		f = partial(uapi_request, request, llm, sor)
		return await env.stream_response(request, f)
