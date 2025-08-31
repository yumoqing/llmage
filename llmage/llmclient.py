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
select a.*, b.hfid, e.ioid
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
	return None

async def inference(request, env):
	uapi = UAPI(request, env)
	params = env.params_kw
	llmid = params.llmid
	prompt = params.prompt
	stream = params.stream or True
	dbname = env.get_module_dbname('llmage')
	db = env.DBPools()
	async with db.sqlorContext(dbname) as sor:
		llm = await get_llm(llmid)
		env.update(llm)
		uapi = UAPI(request, env=env, sor=sor)
		userid = await env.get_user()
		f = partial(uapi.stream_linify, llm.upappid, llm.apiname, userid)
		return await env.stream_response(request, f)
