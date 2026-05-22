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
	get_llms_by_catelog,
	get_llms_sort_by_provider,
	get_llmcatelogs,
	get_llms_by_catelog_to_customer,
	get_llmproviders,
	tpac_accounting,
	get_tpac_balance,
	get_user_tpac_apikey,
	get_llm, 
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
	llm_accounting
)

from .asyncinference import (
	get_asynctask_status,
	query_task_status,
	get_today_asynctask_list
)

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
	env.get_user_tpac_apikey = get_user_tpac_apikey
	env.get_tpac_balance = get_tpac_balance
	env.tpac_accounting = tpac_accounting
	env.get_llms_sort_by_provider = get_llms_sort_by_provider
	env.keling_token = keling_token
	env.llm_query_price = llm_query_price
	env.get_llms_by_catelog_to_customer = get_llms_by_catelog_to_customer
	rf = RegisterFunction()
	rf.register('jimeng_auth_headers', jimeng_auth_headers)

