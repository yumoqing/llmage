from ahserver.serverenv import ServerEnv
from appPublic.dictObject import DictObject
from sqlor.dbpools import get_sor_context
from .accounting import llm_charging, llm_accounting

async def asynctask_callbacka(appname, apiname, params_kw)
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
			llmusage.status = d.status
			if d.status == 'SUCCEEDED':
				llms = await sor.R('llm', {'id': llmusage.llmid})
				if len(llms) == 0:
					e = Exception(f'{llmusage.llmid} llm not found')
					exception(f'{e}')
					raise e
				llm = llms[0]
				if llm.ppid:
					try:
						chargings = await llm_charging(sor, llm.ppid, 
												llmusage.userid, d.usage)
						llmusage.amount = chargings.amount
						llmusage.cost = chargings.cost
					except Exception as e:
						e = Exception(f'{llm.pid} charging error{e}')
						exception(f'{e}')
				else:
					llmusage.amount = 0
					llmusage.cost = 0
				sor.U('llmusage', llmusage)


		except Exception as e:
			e = Exception(f'{uapi.response=}, {params_kw=} render error')
			exception(f'{e}')
			raise e

	if llmusage:
		await llm_accounting(llmusage)

		
