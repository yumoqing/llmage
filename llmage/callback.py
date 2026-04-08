from ahserver.serverenv import ServerEnv
from appPublic.dictObject import DictObject
from sqlor.dbpools import get_sor_context

async def asynctask_callback(appname, apiname, params_kw)
	env = ServerEnv()
	llmusage = None
	async with get_sor_context(env, 'llmage') as sor:
		uapi = await env.sor_get_uapi_by_appname_apiname(appname, apiname)
		try:
			dstr = await env.tmpl_engine.renders(uapi.response, params_kw)
			d = DictObject(**json.loads(dstr))
			llmus = await sor.R('llmusage', {'taskid': d.taskid})
			if len(llmus) == 0:
				e = Exception(f'{d=}, {taskid=} not found')
				exception(f'{e}')
				raise e
			llmusage = llmus[0]
			io = json.loads(llmusage.ioinfo)
			out = io.get('output')
			out.append(d)
			llmusage.ioinfo = json.dumps(io, ensure_ascii=False)
			llmusage.status = d.status
			await sor.U('llmusage', llmusage)

		except Exception as e:
			e = Exception(f'{uapi.response=}, {params_kw=} render error')
			exception(f'{e}')
			raise e

	if llmusage:
		await llm_accounting(llmusage)
		
