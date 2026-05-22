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
from .utils import *

async def llm_charging(ppid, llmusage):
	env = ServerEnv()
	usages =  llmusage.usages
	if isinstance(usages, str):
		usages = json.loads(usages)
	prices = await env.buffered_charging(ppid, usages)
	if prices is None:
		e = Exception(f'{ppid=}, {usages=}{llmusage.id=}  env.buffered_charging() return None')
		exception(f'{e}')
		raise e
		return None
	amount = 0
	cost = 0
	for p in prices:
		amount += p.amount
		if p.cost:
			cost += p.cost
	discount = await env.get_customer_discount(llmusage.ownerid, 
				llmusage.userorgid)
	return DictObject(**{
		'original_amount': amount,
		'amount': amount * discount,
		'cost': cost
	})

async def checkCustomerBalance(llmid, userid, userorgid, catelogid=None):
	if llmid is None:
		debug(f'checkCustomerBalance(): llmid is None')
		return False
	env = ServerEnv()
	llm = await get_llm(llmid)
	if llm.ownerid == userorgid:
		debug(f'self orgid user')
		return True
	balance = 0.00
	tpac = await get_user_tpac(lu.userid)
	if tpac:
		balance = await get_tpac_balance(tpac, userid)
	else:
		async with get_sor_context(env, 'accounting') as sor:
			balance = await getCustomerBalance(sor, userorgid)
	bal = 0 if balance is None else balance
	if llm.min_balance is None:
		llm.min_balance = 0.00
	ret = llm.ppid and llm.min_balance < bal
	debug(f'{llm.ppid=}, {llm.min_balance=}, {bal=}')
	return ret

async def llm_accounting(llmusage):
	env = ServerEnv()
	llmid = llmusage.llmid
	async with get_sor_context(env, 'llmage') as sor:
		sql = """select a.*, b.ppid from llm a, llm_api_map b 
where a.id=${llmid}$ 
	and a.id = b.llmid 
	and b.isdefaultcatelog = '1'
"""
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
	t = time.time()
	dt = datetime.fromtimestamp(t)
	tsstr = dt.strftime('%Y-%m-%d %H:%M:%S.') + f'{dt.microsecond // 1000:03d}'
	async with get_sor_context(env, 'llmage') as sor:
		sql = """select a.*, c.ppid 
from llmusage a, llm b, llm_api_map c
where a.llmid = b.id 
	and a.llmid = c.llmid
	and c.isdefaultcatelog = '1'
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
				try:
					output = await get_lastoutput(r.ioinfo)
				except Exception as e:
					continue
				r.usages = output.get('usage')
			if r.usages is None:
				await llm_accoung_failed(r.id)
				debug(f'{r.usages=} is None')
				continue
			d = None
			try:
				debug(f'{r.ppid=}, {r.usages=} {r.id=}')
				d = await llm_charging(r.ppid, r)

			except Exception as e:
				await llm_accoung_failed(r.id)
				exception(f'{r.ppid=}, {r.usages=} llm_charging() failed,{e}')
				continue
			r.amount = d.amount
			r.cost = d.cost
			ns = {
				'id': r.id,
				'amount': r.amount,
				'cost': r.cost,
				'usage': json.dumps(r.usage, ensure_ascii=False, indent=4)
			}
			await sor.U('llmusage', ns)
			lus.append(r)
	return lus

async def llm_accoung_failed(luid):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		await sor.U('llmusage', {
			'id': luid,
			'accounting_status': 'failed'
		})

async def backend_accounting():
	env = ServerEnv()
	debug(f'backend accounting started ...')
	while True:
		try:
			lus = await get_accounting_llmusages()
		except Exception as e:
			exception(f'{e}')
			lus = []
		# debug(f'{len(lus)=} need to accounting........')
		for lu in lus:
			try:
				debug(f'backend_accounting(): {lu.id=} handleing...')
				# apikey = await get_user_tpac_apikey(lu.userid)
				tpac = await get_user_tpac(lu.userid)
				if tpac:
					await tpac_accounting(tpac, lu.userid, lu.llmid, lu.amount, lu.usages, lu.id)
				else:
					await llm_accounting(lu)
			except Exception as e:
				exception(f'{e}, {lu.id=}')
				await llm_accoung_failed(lu.id)
				

		await asyncio.sleep(10)

