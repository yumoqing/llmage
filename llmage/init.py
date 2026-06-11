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
	get_user_tpac,
	get_tpac_balance,
	get_llm_by_model,
	get_llms_by_catelog,
	get_llms_sort_by_provider,
	get_llmcatelogs,
	get_llms_by_catelog_to_customer,
	get_llmproviders,
	get_llm,
	get_llmage_llm,
	get_llm_catelogs,
	invalidate_uapi_cache,
)

from .llmclient import (
	inference_generator,
	inference 
)
from .accounting import (
	checkCustomerBalance, 
	llm_charging,
	get_accounting_llmusages,
	backend_accounting,
	llm_accounting,
	backup_accounted_llmusage,
	get_failed_accounting_records,
	llm_accoung_failed
)
from .stats import get_llmage_stats

from .asyncinference import (
	get_asynctask_status,
	query_task_status,
	get_today_asynctask_list
)


def _on_hot_reload(data=None):
	"""Event handler for hot_reload — wraps invalidate_uapi_cache to accept dispatcher's data arg."""
	from appPublic.log import debug
	debug(f'[llmage] on_hot_reload called, invalidating uapi cache (data={data})')
	invalidate_uapi_cache()


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
	env.get_llmage_llm = get_llmage_llm
	env.get_llm_catelogs = get_llm_catelogs
	env.invalidate_uapi_cache = invalidate_uapi_cache
	env.inference = inference
	env.get_user_tpac = get_user_tpac
	env.get_tpac_balance = get_tpac_balance
	env.inference_generator = inference_generator
	env.get_llms_by_catelog = get_llms_by_catelog
	env.get_llmcatelogs = get_llmcatelogs
	env.checkCustomerBalance = checkCustomerBalance
	env.get_llmproviders = get_llmproviders
	env.get_llms_sort_by_provider = get_llms_sort_by_provider
	env.keling_token = keling_token
	env.llm_query_price = llm_query_price
	env.get_llms_by_catelog_to_customer = get_llms_by_catelog_to_customer
	env.backup_accounted_llmusage = backup_accounted_llmusage
	env.get_failed_accounting_records = get_failed_accounting_records
	env.get_llmage_stats = get_llmage_stats
	# Bind hot_reload event — module-level function, ref safe (module keeps it alive)
	if hasattr(env, 'event_dispatcher'):
		env.event_dispatcher.bind('hot_reload', _on_hot_reload)
	rf = RegisterFunction()
	rf.register('jimeng_auth_headers', jimeng_auth_headers)

