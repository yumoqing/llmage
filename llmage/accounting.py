import asyncio
import json
import time
from datetime import datetime
from appPublic.log import exception, debug
from appPublic.uniqueID import getID
from appPublic.dictObject import DictObject
from sqlor.dbpools import get_sor_context
from ahserver.serverenv import ServerEnv
from accounting.consume import consume_accounting
from accounting.getaccount import getCustomerBalance

async def llm_charging(ppid, llmusage):
	env = ServerEnv()
	prices = await env.buffered_charging(ppid, llmusage.usages)
	if prices is None:
		e = Exception(f'{ppid=}, {llmusage.usage=}{llmusage.id=}  env.buffered_charging() return None')
		exception(f'{e}')
		raise e
		return None
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
			debug(f'self orgid user')
			return True
		balance = await getCustomerBalance(sor, userorgid)
		bal = 0 if balance is None else balance
		if llm.min_balance is None:
			llm.min_balance = 0.00
		debug(f'{userorgid=}, {balance=}, {llm.min_balance=}, {llm.ppid=}')
		ret = llm.ppid and llm.min_balance < bal
		return ret
	debug(f'{userorgid=} checkCustomerBalance() failed')
	return False

async def llm_accounting(llmusage):
	env = ServerEnv()
	llmid = llmusage.llmid
	async with get_sor_context(env, 'llmage') as sor:
		sql = "select * from llm where id=${llmid}$"
		recs = await sor.sqlExe(sql, {'llmid': llmusage.llmid})
		if len(recs) == 0:
			ns = {
				'id': llmusage.id,
				'accounting_status': 'failed'
			}
			await sor.U('llmusage', ns)
			e = Exception(f'llm not found({llmid})')
			exception(f'{e}')
			raise e
		if recs[0].ppid is None:
			ns = {
				'id': llmusage.id,
				'accounting_status': 'failed'
			}
			await sor.U('llmusage', ns)
			e = Exception(f'llm ({llmid}) donot has a pricing_program')
			exception(f'{e}')
			raise e
		customerid = llmusage.userorgid
		userid = llmusage.userid
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
		llmusage.accounting_status = 'accounted'
		ns = {
			'id': llmusage.id,
			'accounting_status': 'accounted'
		}
		await sor.U('llmusage', ns)

async def get_accounting_llmusages(luid=None):
	env = ServerEnv()
	lus = []
	t = time.time() - 20
	dt = datetime.fromtimestamp(t)
	tsstr = dt.strftime('%Y-%m-%d %H:%M:%S.') + f'{dt.microsecond // 1000:03d}'
	async with get_sor_context(env, 'llmage') as sor:
		sql = """select a.*, b.ppid 
from llmusage a, llm b 
where a.llmid = b.id 
	and a.status = 'SUCCEEDED'
	and a.use_time < ${tsstr}$
	and a.accounting_status='created'"""
		ns = {'tsstr': tsstr}
		if luid:
			sql += " and a.id=${luid}$"
			ns['luid'] = luid
		recs = await sor.sqlExe(sql, ns)
		# debug(f'{sql=}, {ns=}, {len(recs)=}')
		for r in recs:
			if r.usages is None:
				io = json.loads(r.ioinfo)
				if len(io['output']) == 0:
					llmusage.accounting_status = 'failed'
					await sor.U('llmusage', {'id': llmusage.id, 'accounting_status': 'failed'})
					debug(f'{len(io["output"])} is 0')
					continue
				r.usages = io['output'][-1]['usage']
			if r.usages is None:
				llmusage.accounting_status = 'failed'
				await sor.U('llmusage', {'id': llmusage.id, 'accounting_status': 'failed'})
				debug(f'{r.usages=} is None')
				continue
			try:
				if isinstance(r.usages, str):
					r.usages = json.loads(r.usages)
				d = await llm_charging(sor, r.ppid, r)
			except Exception as e:
				await sor.U('llmusage', {'id': r.id, 'accounting_status': 'failed'})
				debug(f'{r.ppid=}, {r.usages=} llm_charging() failed')
				continue
			r.amount = d.amount
			r.cost = d.cost
			await sor.U('llmusage', r.copy())
			lus.append(r)
	return lus

async def backend_accounting():
	env = ServerEnv()
	debug(f'backend accounting started ...')
	while True:
		try:
			lus = await get_accounting_llmusages()
		except Exception as e:
			exception(f'{e}')
			lus = []
		for lu in lus:
			try:
				debug(f'backend_accounting(): {lu.id=} handleing...')
				await llm_accounting(lu)
			except Exception as e:
				exception(f'{e}, {lu.id=}')

		await asyncio.sleep(10)

