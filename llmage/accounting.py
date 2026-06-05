import asyncio
import json
import time
from datetime import datetime, timedelta
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
	llm = await get_llmage_llm(llmid)
	if llm.ownerid == userorgid:
		debug(f'self orgid user')
		return True
	balance = 0.00
	tpac = await get_user_tpac(userid)
	if tpac:
		debug(f'{tpac=}, get tpac balance')
		balance = await get_tpac_balance(tpac, userid)
	else:
		debug(f'{tpac=}, get local balance')
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
	llm = await get_llmage_llm(llmid)
	if llm is None:
		async with get_sor_context(env, 'llmage') as sor:
			ns = {
				'id': llmusage.id,
				'accounting_status': 'failed'
			}
			await sor.U('llmusage', ns)
		e = Exception(f'llm not found({llmid})')
		exception(f'{e}')
		raise e
	if llm.ppid is None:
		async with get_sor_context(env, 'llmage') as sor:
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
	resellerid = llm.ownerid
	providerid = llm.providerid
	trans_amount = llmusage.amount
	trans_cost = llmusage.cost
	async with get_sor_context(env, 'llmage') as sor:
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
		sql = """select a.*, b.model, c.ppid 
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
				debug(f'{r.usages=} is None, accoiunting failed')
				await llm_accoung_failed(r.id, reason='usages is None')
				continue
			d = None
			try:
				debug(f'{r.ppid=}, {r.usages=} {r.id=}')
				d = await llm_charging(r.ppid, r)

			except Exception as e:
				exception(f'{r.ppid=}, {r.usages=} llm_charging() failed,{e}')
				await llm_accoung_failed(r.id, reason=f'llm_charging failed: {e}')
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

async def llm_accoung_failed(luid, reason=None):
	env = ServerEnv()
	async with get_sor_context(env, 'llmage') as sor:
		await sor.U('llmusage', {
			'id': luid,
			'accounting_status': 'failed'
		})
		# Also record in the failed accounting table for tracking
		recs = await sor.R('llmusage', {'id': luid})
		if recs:
			r = recs[0]
			failed_id = getID()
			failed_rec = {
				'id': failed_id,
				'llmusageid': luid,
				'llmid': r.llmid,
				'userid': r.userid,
				'userorgid': r.userorgid,
				'use_date': r.use_date,
				'use_time': r.use_time,
				'amount': r.amount,
				'cost': r.cost,
				'failed_reason': reason or 'accounting failed',
				'failed_time': env.timestampstr(),
				'retry_count': 0,
				'handled': '0'
			}
			await sor.C('llmusage_accounting_failed', failed_rec)


async def backup_accounted_llmusage(cutoff_date):
	"""Backup accounted records with use_date < cutoff_date to history table."""
	env = ServerEnv()
	ts = env.timestampstr()
	async with get_sor_context(env, 'llmage') as sor:
		# Step 0: Count records to backup
		count_sql = """SELECT COUNT(*) as cnt FROM llmusage
WHERE accounting_status='accounted' AND use_date < ${cutoff_date}$"""
		count_recs = await sor.sqlExe(count_sql, {'cutoff_date': cutoff_date})
		total = count_recs[0].cnt if count_recs else 0
		if total == 0:
			debug(f'backup_accounted_llmusage: no records to backup for use_date < {cutoff_date}')
			return 0
		debug(f'backup_accounted_llmusage: {total} records to backup')
		
		# Step 1: INSERT INTO history SELECT from main table
		insert_sql = """INSERT INTO llmusage_history 
(id, llmid, use_date, use_time, userid, usages, ioinfo, transno, responsed_seconds, finish_seconds, status, taskid, amount, cost, userorgid, ownerid, accounting_status, backup_time)
SELECT id, llmid, use_date, use_time, userid, usages, ioinfo, transno, responsed_seconds, finish_seconds, status, taskid, amount, cost, userorgid, ownerid, accounting_status, ${ts}$
FROM llmusage
WHERE accounting_status='accounted' AND use_date < ${cutoff_date}$"""
		await sor.execute(insert_sql, {'cutoff_date': cutoff_date, 'ts': ts})
		debug(f'backup_accounted_llmusage: inserted {total} records to history')
		
		# Step 2: DELETE from main table
		delete_sql = """DELETE FROM llmusage
WHERE accounting_status='accounted' AND use_date < ${cutoff_date}$"""
		await sor.execute(delete_sql, {'cutoff_date': cutoff_date})
		debug(f'backup_accounted_llmusage: deleted {total} records from main table')
	
	return total


async def get_failed_accounting_records(filters=None, page=1, page_size=50):
	"""Search failed accounting records with optional filters.
	
	filters: dict with optional keys:
		- userorgid: filter by user organization
		- llmid: filter by model ID
		- handled: '0' or '1'
		- start_date: filter use_date >= start_date
		- end_date: filter use_date <= end_date
	"""
	async with get_sor_context(ServerEnv(), 'llmage') as sor:
		conditions = []
		ns = {}
		if filters:
			if filters.get('userorgid'):
				conditions.append("userorgid=${userorgid}$")
				ns['userorgid'] = filters['userorgid']
			if filters.get('llmid'):
				conditions.append("llmid=${llmid}$")
				ns['llmid'] = filters['llmid']
			if filters.get('handled') is not None:
				conditions.append("handled=${handled}$")
				ns['handled'] = filters['handled']
			if filters.get('start_date'):
				conditions.append("use_date>=${start_date}$")
				ns['start_date'] = filters['start_date']
			if filters.get('end_date'):
				conditions.append("use_date<=${end_date}$")
				ns['end_date'] = filters['end_date']
		where = ""
		if conditions:
			where = "where " + " and ".join(conditions)
		# Count total
		count_sql = f"select count(*) as cnt from llmusage_accounting_failed {where}"
		count_recs = await sor.sqlExe(count_sql, ns)
		total = count_recs[0].cnt if count_recs else 0
		# Query with pagination
		offset = (page - 1) * page_size
		query_sql = f"""select * from llmusage_accounting_failed {where} 
order by failed_time desc limit {page_size} offset {offset}"""
		recs = await sor.sqlExe(query_sql, ns)
		return {
			'total': total,
			'page': page,
			'page_size': page_size,
			'records': recs
		}

async def backend_accounting():
	env = ServerEnv()
	debug(f'backend accounting started ...')
	last_backup_date = None
	while True:
		try:
			lus = await get_accounting_llmusages()
		except Exception as e:
			exception(f'{e}')
			lus = []
		for lu in lus:
			try:
				tpac = await get_user_tpac(lu.userid)
				if tpac:
					debug(f'{lu.id=},{lu.userid=}, {tpac=}, go tpac')
					await tpac_accounting(tpac, lu.userid, lu.llmid, lu.amount, lu.usages, lu.id, lu.model)
				else:
					debug(f'{lu.id=},{lu.userid=}, {tpac=}, go local')
					await llm_accounting(lu)
			except Exception as e:
				exception(f'{e}, {lu.id=}')
				await llm_accoung_failed(lu.id, reason=str(e))

		# Check if date changed, trigger backup once per day
		today = datetime.now().strftime('%Y-%m-%d')
		if today != last_backup_date:
			yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
			last_backup_date = today
			try:
				debug(f'date changed to {today}, triggering backup for use_date < {yesterday}')
				await backup_accounted_llmusage(yesterday)
			except Exception as e:
				exception(f'backup_accounted_llmusage failed: {e}')

		await asyncio.sleep(10)

