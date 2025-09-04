import json
from random import randint
from functools import partial
from traceback import format_exc
from sqlor.dbpools import DBPools
from appPublic.log import debug, exception
from uapi.appapi import UAPI, sor_get_callerid, sor_get_uapi
from ahserver.serverenv import get_serverenv

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

async def uapi_request(request, sor, caller_orgid, callerid, uapi, llm, params):
	userid = await get_owner_userid(sor, llm)
	txt = ''
	async for l in uapi.stream_linify(llm.upappid, llm.apiname, userid, params=params):
		if l and l != '[DONE]':
			d = json.loads(l)
			if d['content'] != '':
				txt = txt + d['content']
				yield l
	debug(f'{d=}, {txt=}')
	
def b64media(meidafile):
	if meidafile.startswith('data:'):
		return meidafile
	fs = FileStorage()
	fn = fs.realPath(meidafile)
	with open(fn, 'rb') as f:
		b = f.read()
		return base64.b64encode(b).decode('iso-8859-1')

async def inference(request, *args, **kw):
	env = request._run_ns
	caller_orgid = await env.get_userorgid()
	callerid = await env.get_user()
	params = env.params_kw
	llmid = params.llmid
	prompt = params.prompt
	stream = params.stream or True
	dbname = env.get_module_dbname('llmage')
	db = env.DBPools()
	async with db.sqlorContext(dbname) as sor:
		llm = await get_llm(llmid)
		env.update(llm)
		uapi = UAPI(request, sor=sor)
		userid = await env.get_user()
		f = partial(uapi_request, request, sor, caller_orgid, callerid, uapi, llm, params=params)
		return await env.stream_response(request, f)
