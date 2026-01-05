from appPublic.log import exception, debug
from appPublic.uniqueID import getID
from appPublic.dictObject import DictObject
from sqlor.dbpools import get_sor_context
from pricing.pricing import pricing_program_charging
from accounting.consume import consume_accounting

async def llm_accounting(request, llmid, 
			usage, customerid, userid, orderid=None):
	env = request._run_ns
	async with get_sor_context(request._run_ns, 'llmage') as sor:
		sql = "select * from llm where id=${llmid}$"
		recs = await sor.sqlExe(sql, {'llmid': llmid})
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
		charges = await pricing_program_charging(sor, recs[0].ppid, usage)
		trans_amount = trans_cost = 0
		for c in charges:
			trans_amount += c.amount
			trans_cost += c.cost
		biz_date = await env.get_business_date(sor)
		timestamp = env.timestampstr()
		if orderid is None:
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
		ais = [
			ai0, ai1	
		]
		await consume_accounting(sor, orderid, ais)

