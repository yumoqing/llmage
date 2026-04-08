import asyncio
from appPublic.base64_to_file import hex2base64
from appPublic.registerfunction import RegisterFunction
from ahserver.serverenv import ServerEnv
from ahserver.configuredServer import add_cleanupctx
from .keling import keling_token
from .jimeng import jimeng_auth_headers
from .utils import (
	llm_query_orders,
	llm_query_price,
	get_llm_by_model
)

from .llmclient import (
	b64media2url,
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

async def start_backend(app):
	task = asyncio.create_task(backend_accounting())
	yield
	task.cancel()

def load_llmage():
	env = ServerEnv()
	env.llm_query_orders = llm_query_orders
	env.get_llm_by_model = get_llm_by_model
	env.llm_charging = llm_charging
	env.get_accounting_llmusages = get_accounting_llmusages
	env.llm_accounting = llm_accounting
	env.get_today_asynctask_list = get_today_asynctask_list
	env.get_asynctask_status = get_asynctask_status
	env.query_task_status = query_task_status
	env.get_llm = get_llm
	env.b64media2url = b64media2url
	env.hex2base64 = hex2base64
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
	add_cleanupctx(start_backend)
