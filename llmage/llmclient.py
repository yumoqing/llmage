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
	db = DBPools()
	dbname = get_serverenv('get_module_dbname')('llmage')
	async with db.sqlorContext(dbname) as sor:
		recs = await sor.R('llm', {'catelogid': catelogid})
		return recs
	return []
	
async def get_llm(llmid):
	db = DBPools()
	dbname = get_serverenv('get_module_dbname')('llmage')
	async with db.sqlorContext(dbname) as sor:
		sql = """select a.*,
d.input_fields,
d.input_view, 
d.output_view, 
c.system_message, 
c.user_message,
c.assisant_message 
from llm a, llmcatelog b 
	left join historyformat c on b.hfid = c.id
	left join uapiio d on b.ioid = d.id
where a.llmcatelogid = b.id
	and a.id = ${llmid}$	
"""
		recs = await sor.sqlExe(sql, {'llmid': llmid})
		if len(recs) > 0:
			r = recs[0]
			apis = await sor_get_uapi(sor, r.upappid, r.apiname)
			if len(apis) == 0:
				e = Exception(f'{r.upappid=},{r.apiname=} uapi not found')
				exception(f'{e=}\n{format_exc()}')
				raise e
			api = apis[0]
			r.inputfields = api.paramsdesc
			return recs[0]
	return None

async def inference(request, env):
	uapi = UAPI(request, env)
	params = env.params_kw
	llmid = params.id
	prompt = params.prompt
	stream = params.stream or True
	dbname = env.get_module_dbname('llmage')
	db = env.DBPools()
	async with db.sqlorContext(dbname) as sor:
		llms = await sor.R('llm', {'id':llmid})
		if len(llms) == 0:
			e = Exception(f'{llmid=} not found')
			exception(f'{e}\n{format_exc()}')
			raise e
		llm = llms[0]
		uapi = UAPI(request, env=env, sor=sor)
		return env.stream_response(request, 
			uapi.stream_linify(llm.upappid, llm.apiname, env.user))
