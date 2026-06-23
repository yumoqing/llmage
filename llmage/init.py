import asyncio
from appPublic.registerfunction import RegisterFunction
from sqlor.dbpools import DBPools, get_sor_context
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

from .product_interface import (
	get_product_display,
	check_product_availability,
	check_product_consumable,
	execute_product_service,
	execute_product_service_stream,
	calculate_product_cost,
)


async def load_product_category_product(parent_category_id):
	"""Load llmage catalogs and published models as product sub-categories and products.

	Called by product_management.import_categories_and_products() when resource_module='llmage'.
	Responsible for reading source data AND writing to product_management tables.
	"""
	import time
	from appPublic.uniqueID import getID

	env = ServerEnv()
	pm_dbname = env.get_module_dbname('product_management')

	# Step 1: Read source data from llmage
	async with get_sor_context(env, 'llmage') as sor:
		catelogs = await sor.R('llmcatelog', {})
		if not catelogs:
			return {'success': False, 'error': 'llmage中没有产品类别数据'}

		llm_sql = """select a.id, a.name, a.model, a.description, a.status,
m.llmcatelogid, lc.name as catelogname
from llm a
join llm_api_map m on a.id = m.llmid
join llmcatelog lc on m.llmcatelogid = lc.id
where m.isdefaultcatelog = '1' and a.status = 'published'
order by lc.sort_order, lc.name, a.name"""
		llms = await sor.sqlExe(llm_sql, {})

	# Step 2: Get parent category's org_id from product_management
	now = time.strftime('%Y-%m-%d %H:%M:%S')
	async with DBPools().sqlorContext(pm_dbname) as sor:
		parent_rows = await sor.sqlExe(
			"SELECT org_id FROM product_category WHERE id = ${id}$",
			{'id': parent_category_id}
		)
		if not parent_rows:
			return {'success': False, 'error': f'父类别 {parent_category_id} 不存在'}
		org_id = parent_rows[0].org_id

	# Step 3: Write sub-categories and products
	source_to_id = {}
	created_cats = 0
	skipped_cats = 0
	created_prods = 0
	skipped_prods = 0

	async with DBPools().sqlorContext(pm_dbname) as sor:
		for c in catelogs:
			existing = await sor.sqlExe(
				"""SELECT id FROM product_category
				   WHERE name = ${name}$ AND parent_id = ${parent_id}$ AND org_id = ${org_id}$""",
				{'name': c.name, 'parent_id': parent_category_id, 'org_id': org_id}
			)
			if existing:
				source_to_id[c.id] = existing[0].id
				skipped_cats += 1
				continue

			new_id = getID()
			source_to_id[c.id] = new_id
			cat_data = {
				'id': new_id,
				'parent_id': parent_category_id,
				'name': c.name,
				'description': getattr(c, 'description', '') or '',
				'has_product': '1',
				'product_type': 'llm_model',
				'product_type_title': '大模型按量',
				'sort_order': str(getattr(c, 'sort_order', 0) or 0),
				'icon': '',
				'status': '1',
				'resource_module': 'llmage',
				'org_id': org_id,
				'created_at': now,
				'updated_at': now
			}
			await sor.C('product_category', cat_data)
			created_cats += 1

		for llm in (llms or []):
			target_cat_id = source_to_id.get(llm.llmcatelogid)
			if not target_cat_id:
				skipped_prods += 1
				continue

			existing_prod = await sor.sqlExe(
				"""SELECT id FROM product
				   WHERE product_code = ${code}$ AND org_id = ${org_id}$""",
				{'code': llm.model, 'org_id': org_id}
			)
			if existing_prod:
				skipped_prods += 1
				continue

			prod_id = getID()
			prod_data = {
				'id': prod_id,
				'category_id': target_cat_id,
				'product_code': llm.model,
				'resource_ref_id': llm.id,
				'product_name': llm.name,
				'product_type': 'llm_model',
				'brief_intro': getattr(llm, 'description', '') or '',
				'status': '1',
				'price_type': '1',
				'price': '0',
				'currency': 'CNY',
				'sort_order': '0',
				'org_id': org_id,
				'created_at': now,
				'updated_at': now
			}
			await sor.C('product', prod_data)
			created_prods += 1

	return {
		'success': True,
		'message': f'llmage导入完成: 新增 {created_cats} 个子类别, {created_prods} 个产品; '
				   f'跳过 {skipped_cats} 个已存在类别, {skipped_prods} 个已存在产品'
	}


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
	# Product module standard interface
	env.product_interface = {
		'module_name': 'llmage',
		'get_product_display': get_product_display,
		'check_product_availability': check_product_availability,
		'check_product_consumable': check_product_consumable,
		'execute_product_service': execute_product_service,
		'execute_product_service_stream': execute_product_service_stream,
		'calculate_product_cost': calculate_product_cost,
		'load_product_category_product': load_product_category_product,
	}
	# Bind hot_reload event — module-level function, ref safe (module keeps it alive)
	if hasattr(env, 'event_dispatcher'):
		env.event_dispatcher.bind('hot_reload', _on_hot_reload)
	rf = RegisterFunction()
	rf.register('jimeng_auth_headers', jimeng_auth_headers)

