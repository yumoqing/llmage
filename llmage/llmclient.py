from traceback import format_exc
from appPublic.log import debug, exception
from uapi.appapi import UAPI
from ahserver.serverenv get_serverenv

async def inference(request, env):
	uapi = UAPI(request, env)
	params = env.params_kw
	llmid = params.id
	prompt = params.prompt
	stream = prompt.stream or True
	dbname = env.get_module_dbname('llmage')
	db = env.DBPools()
	async with db.sqlorContext(dbname) as sor:
		llms = await sor.R('llm', {'id':llmid})
		if len(llms) == 0:
			e = Exception(f'{llmid=} not found')
			exception(f'{e}\n{format_exc()}')
			raise e
		uapi = UAPI(request, env=env, sor=sor)
		return env.stream_response(request, 
			uapi.stream_linify(llms[0].
