import json
import asyncio
from random import randint
from functools import partial
from traceback import format_exc
from sqlor.dbpools import DBPools
from appPublic.log import debug, exception
from appPublic.uniqueID import getID
from appPublic.dictObject import DictObject
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
		recs = await sor.R('llm', {'llmcatelogid': catelogid})
		return recs
	return []
	
async def get_llm(llmid):
	db = DBPools()
	dbname = get_serverenv('get_module_dbname')('llmage')
	async with db.sqlorContext(dbname) as sor:
		sql = """select x.*,
z.input_fields,
z.input_view, 
z.output_view, 
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
) x left join historyformat y on x.hfid = y.id
	left join uapiio z on x.ioid = z.id
where x.id = ${llmid}$	
"""
		recs = await sor.sqlExe(sql, {'llmid': llmid})
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
	async for l in uapi.stream_linify(llm.upappid, llm.apiname, userid, 
				params=env.params_kw):
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
			if yield_it:
				yield l
			else:
				debug(f'{l} not yield')
	debug(f'{l=}, {txt=}')
	
async def async_uapi_request(request, llm, sor):
	env = request._run_ns.copy()
	caller_orgid = await env.get_userorgid()
	callerid = await env.get_user()
	uapi = UAPI(request, sor=sor)
	userid = await get_owner_userid(sor, llm)
	b = await uapi.call(llm.upappid, llm.apiname, userid, params=env.params_kw)
	if isinstance(b, bytes):
		b = b.decode('utf-8')
	debug(f'task sumbited:{b}')
	d = json.loads(b)
	if not d.get('taskid'):
		debug(f'{b} error')
		yield '{"content":"server return no taskid"}\n'
		return
	uapi = UAPI(request, sor=sor)
	while True:
		b = await uapi.call(llm.upappid, llm.query_apiname, userid, 
				params={
					"taskid": d.get('taskid')
				}
		)
		if isinstance(b, bytes):
			b = b.decode('utf-8')
		b = ''.join(b.split('\n'))
		debug(f'response line = {b}')
		rzt = DictObject(**json.loads(b))
		yield b + '\n'
		if not rzt.status or rzt.status == 'FAILED':
			debug(f'{b=} return error')
			return
		if rzt.status == 'SUCCEEDED':
			debug(f'{b=} return successed')
			await asyncio.sleep(1)
			return
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
		if llm.query_apiname:
			f = partial(async_uapi_request, request, llm, sor)
			return await env.stream_response(request, f)

		env.update(llm)
		uapi = UAPI(request, sor=sor)
		f = partial(uapi_request, request, llm, sor)
		return await env.stream_response(request, f)
