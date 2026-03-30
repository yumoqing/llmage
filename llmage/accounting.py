from appPublic.log import exception, debug
from appPublic.uniqueID import getID
from appPublic.dictObject import DictObject
from sqlor.dbpools import get_sor_context
from ahserver.serverenv import ServerEnv
# from pricing.pricing import pricing_program_charging
from accounting.consume import consume_accounting
from accounting.getaccount import getCustomerBalance

async def llm_charging(sor, ppid, llmusage):
	env = ServerEnv()
	prices = await env.pricing_program_charging(sor, ppid, llmusage.usage)
	if not pricing:
		d = DictObject()
		d.original_amount = d.amount = d.cost = 0.00
		return d
	amount = 0
	cost = 0
	for p in prices:
		amount += p.amount
		if p.cost:
			cost += p.cost
	discount = await env.sor_get_customer_discount(sor, 
				llmusage.ownerid, 
				llmusage.userorgid)
	return DictObject(**{
		'original_amount': amount,
		'amount': amount * discount,
		'cost': cost
	})

async def checkCustomerBalance(llmid, userorgid):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		llms = await sor.R('llm', { 'id': llmid})
		if len(llms) < 1:
			e = Exception(f'llm({llmid}) not exists')
			exception(f'{e}')
			raise e
		llm = llms[0].copy()
		if llm.ownerid == userorgid:
			return True
		balance = await getCustomerBalance(sor, userorgid)
		bal = 0 if balance is None else balance
		if llm.min_balance is None:
			llm.min_balance = 0.00
		ret = llm.ppid and llm.min_balance < bal
		debug(f'{llms=},{userorgid=},{balance=},{ret=}')
		return ret
	return False

async def llm_accounting(request, llmusage):
	env = request._run_ns
	async with get_sor_context(request._run_ns, 'llmage') as sor:
		sql = "select * from llm where id=${llmid}$"
		recs = await sor.sqlExe(sql, {'llmid': llmusage.llmid})
		if len(recs) == 0:
			e = Exception(f'llm not found({llmid})')
			exception(f'{e}')
			raise e
		if recs[0].ppid is None:
			e = Exception(f'llm ({llmid}) donot has a pricing_program')
			exception(f'{e}')
			raise e
		resellerid = recs[0].ownerid
		providerid = recs[0].providerid
		trans_amount = llmusage.amount
		trans_cost = llmusage.cost
		biz_date = await env.get_business_date(sor)
		timestamp = env.timestampstr()
		orderid = getID()
		order = {
			"id": orderid,
			"customerid": customerid,
			"resellerid": resellerid,
			"order_date": biz_date,
			"order_status": "1",  # accounted
			"business_op": "PAY",
			"amount": trans_amount,
			"userid": userid,
			"productid": llmid
		}
		await sor.C('biz_order', order)
		orderdetail = {
			"id": getID(),
			"orderid": orderid,
			"productid": llmid,
			"product_cnt": 1,
			"trans_amount": trans_amount
		}
		await sor.C('biz_orderdetail', orderdetail)
		ais = []
		if customerid != resellerid:
			ai0 = DictObject()
			ai0.action = 'PAY'
			ai0.customerid = customerid
			ai0.resellerid = resellerid
			ai0.providerid = providerid
			ai0.biz_date = biz_date
			ai0.timestamp = timestamp
			ai0.productid = llmid
			ai0.transamt = trans_amount
			ai0.variable = {
				"交易金额": trans_amount,
				"交易手续费": 0
			}
			ais.append(ai0)
		ai1 = DictObject()
		ai1.action = 'PAY*'
		ai1.customerid = customerid
		ai1.resellerid = resellerid
		ai1.providerid = providerid
		ai1.biz_date = biz_date
		ai1.timestamp = timestamp
		ai1.providerid = providerid
		ai1.productid = llmid
		ai1.transamt = trans_cost
		ai1.variable = {
			"采购成本": trans_cost
		}
		ais.append(ai1)
		await consume_accounting(sor, orderid, ais)

