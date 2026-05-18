import asyncio
from appPublic.registerfunction import RegisterFunction
from sqlor.dbpools import DBPools
from ahserver.serverenv import ServerEnv
from appPublic.log import debug
from .keling import keling_token
from .jimeng import jimeng_auth_headers
from .utils import (
	llm_query_orders,
	read_webpath,
	llm_query_price,
	get_llm_by_model,
	BufferedLLMs
)

from .llmclient import (
	get_llm, 
	inference_generator,
	inference, 
	get_llmproviders,
	get_llms_sort_by_provider,
	get_llmcatelogs,
	get_llms_by_catelog
)
from .accounting import (
	checkCustomerBalance, 
	llm_charging,
	get_accounting_llmusages,
	backend_accounting,
	llm_accounting
)

from .asyncinference import (
	get_asynctask_status,
	query_task_status,
	get_today_asynctask_list
)

def _bind_llmage_events(dbpools, dbname):
	"""Bind database events to Llmage cache invalidation handlers."""
	bindings = [
		# llm 表增删改：清除 LLM 配置缓存
		(f'{dbname}.llm:c:after', BufferedLLMs.clear_cache),
		(f'{dbname}.llm:u:after', BufferedLLMs.clear_cache),
		(f'{dbname}.llm:d:after', BufferedLLMs.clear_cache),
		# llmcatelog 表变更：清除缓存
		(f'{dbname}.llmcatelog:c:after', BufferedLLMs.clear_cache),
		(f'{dbname}.llmcatelog:u:after', BufferedLLMs.clear_cache),
		(f'{dbname}.llmcatelog:d:after', BufferedLLMs.clear_cache),
		# llm_catalog_rel 关联表变更：清除缓存
		(f'{dbname}.llm_catalog_rel:c:after', BufferedLLMs.clear_cache),
		(f'{dbname}.llm_catalog_rel:u:after', BufferedLLMs.clear_cache),
		(f'{dbname}.llm_catalog_rel:d:after', BufferedLLMs.clear_cache),
	]
	for event_name, handler in bindings:
		dbpools.bind(event_name, handler)
		debug(f'Llmage event bound: {event_name}')

def load_llmage():
	env = ServerEnv()
	env.llm_query_orders = llm_query_orders
	env.read_webpath = read_webpath
	env.get_llm_by_model = get_llm_by_model
	env.llm_charging = llm_charging
	env.get_accounting_llmusages = get_accounting_llmusages
	env.llm_accounting = llm_accounting
	env.get_today_asynctask_list = get_today_asynctask_list
	env.get_asynctask_status = get_asynctask_status
	env.query_task_status = query_task_status
	env.get_llm = get_llm
	env.inference = inference
	env.inference_generator = inference_generator
	env.get_llms_by_catelog = get_llms_by_catelog
	env.get_llmcatelogs = get_llmcatelogs
	env.checkCustomerBalance = checkCustomerBalance
	env.get_llmproviders = get_llmproviders
	env.get_llms_sort_by_provider = get_llms_sort_by_provider
	env.keling_token = keling_token
	env.llm_query_price = llm_query_price
	rf = RegisterFunction()
	rf.register('jimeng_auth_headers', jimeng_auth_headers)

	# Bind database events for automatic cache invalidation
	dbpools = DBPools()
	dbname = env.get_module_dbname('llmage')
	if dbname:
		_bind_llmage_events(dbpools, dbname)
		debug(f'Llmage event listeners bound for database: {dbname}')
	else:
		debug('Llmage event listeners skipped: no database configured for llmage module')
