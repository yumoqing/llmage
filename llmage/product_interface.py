"""
llmage Product Module Interface Implementation

Implements the standard resource module interface for product_management.
All functions take resource_ref_id (= llm.id) as the primary identifier.
The product module stores this mapping in product.resource_ref_id.
"""
import json
import time
from appPublic.log import debug, exception
from appPublic.uniqueID import getID
from appPublic.dictObject import DictObject
from appPublic.timeUtils import curDateString, timestampstr
from sqlor.dbpools import get_sor_context
from ahserver.serverenv import ServerEnv
from .utils import (
    get_llmage_llm,
    get_llm,
    get_user_tpac,
    get_tpac_balance,
    write_llmio,
    write_llmusage,
)
from .accounting import llm_charging


async def _resolve_llm(resource_ref_id):
    """Resolve resource_ref_id (llm.id) to llm record with full info.
    Returns (llm_record, error_message).
    """
    llm = await get_llmage_llm(resource_ref_id)
    if not llm:
        return None, f'模型 {resource_ref_id} 不存在或配置不完整'
    return llm, None


async def get_product_display(resource_ref_id):
    """获取产品定价展示信息。

    Args:
        resource_ref_id: 资源模块内部ID（= llm.id）

    Returns:
        {'success': True, 'pricing_text': str, 'pricing_detail': dict, 'extra_info': dict}
    """
    llm, err = await _resolve_llm(resource_ref_id)
    if err:
        return {'success': False, 'message': err}

    env = ServerEnv()
    pricing_text = ''
    pricing_detail = {}

    if llm.ppid:
        try:
            pd = await env.get_pricing_display(llm.ppid)
            if pd:
                pricing_text = pd.get('display_text', '')
                pricing_detail = pd
        except Exception as e:
            debug(f'get_pricing_display failed for ppid={llm.ppid}: {e}')
            pricing_text = '定价信息暂不可用'

    # Get provider name
    provider_name = ''
    if llm.providerid:
        async with get_sor_context(env, 'rbac') as sor:
            org_recs = await sor.R('organization', {'id': llm.providerid})
            if org_recs:
                provider_name = org_recs[0].orgname

    extra_info = {
        'provider': provider_name,
        'llmid': llm.id,
        'model': llm.model,
        'catelog': getattr(llm, 'catelogname', ''),
        'ownerid': llm.ownerid,
    }

    return {
        'success': True,
        'pricing_text': pricing_text,
        'pricing_detail': pricing_detail,
        'extra_info': extra_info,
    }


async def check_product_availability(resource_ref_id, user_org_id=None):
    """检查产品是否可用（定价方案是否有效）。

    Args:
        resource_ref_id: 资源模块内部ID（= llm.id）
        user_org_id: 用户组织ID（自有模型免检）

    Returns:
        {'available': bool, 'reason': str}
    """
    llm, err = await _resolve_llm(resource_ref_id)
    if err:
        return {'available': False, 'reason': err}

    # Self-owned model: always available
    if user_org_id and llm.ownerid == user_org_id:
        return {'available': True, 'reason': ''}

    # Check status
    if llm.status != 'published':
        return {'available': False, 'reason': '模型已下线'}

    # Check ppid exists
    if not llm.ppid:
        return {'available': False, 'reason': '无定价方案(ppid为空)'}

    # Check pricing data for today
    env = ServerEnv()
    try:
        await env.get_ppid_pricing(llm.ppid)
    except Exception as e:
        debug(f'check_product_availability: ppid={llm.ppid} no pricing: {e}')
        return {'available': False, 'reason': '今日无有效定价数据'}

    return {'available': True, 'reason': ''}


async def check_product_consumable(resource_ref_id, user_id, user_org_id):
    """消费前综合预检：可用性 + 余额 + 定价。

    Args:
        resource_ref_id: 资源模块内部ID（= llm.id）
        user_id: 用户ID
        user_org_id: 用户组织ID

    Returns:
        {'consumable': bool, 'reason': str, 'min_balance': float, 'pricing_available': bool}
    """
    llm, err = await _resolve_llm(resource_ref_id)
    if err:
        return {'consumable': False, 'reason': err,
                'min_balance': 0, 'pricing_available': False}

    # Self-owned model: skip balance check
    if llm.ownerid == user_org_id:
        return {'consumable': True, 'reason': '',
                'min_balance': 0, 'pricing_available': True}

    # Check ppid
    if not llm.ppid:
        return {'consumable': False, 'reason': '无定价方案',
                'min_balance': 0, 'pricing_available': False}

    # Check pricing data
    env = ServerEnv()
    pricing_available = True
    try:
        await env.get_ppid_pricing(llm.ppid)
    except Exception as e:
        debug(f'check_product_consumable: ppid={llm.ppid} no pricing: {e}')
        pricing_available = False
        return {'consumable': False, 'reason': '今日无有效定价数据',
                'min_balance': float(llm.min_balance or 0),
                'pricing_available': False}

    # Check balance
    min_balance = float(llm.min_balance or 0)
    balance = 0.0
    tpac = await get_user_tpac(user_id)
    if tpac:
        balance = await get_tpac_balance(tpac, user_id)
        if balance is None:
            balance = 0.0
    else:
        from accounting.getaccount import getCustomerBalance
        async with get_sor_context(env, 'accounting') as sor:
            bal = await getCustomerBalance(sor, user_org_id)
            balance = float(bal) if bal else 0.0

    if balance < min_balance:
        return {'consumable': False,
                'reason': f'余额不足(当前{balance:.2f}, 最低{min_balance:.2f})',
                'min_balance': min_balance,
                'pricing_available': pricing_available}

    return {'consumable': True, 'reason': '',
            'min_balance': min_balance,
            'pricing_available': pricing_available}


async def execute_product_service(resource_ref_id, user_id, user_org_id, request_data):
    """执行大模型API调用（非流式）。

    Args:
        resource_ref_id: 资源模块内部ID（= llm.id）
        user_id: 用户ID
        user_org_id: 用户组织ID
        request_data: dict, 请求参数（messages, temperature, max_tokens 等）

    Returns:
        {'success': True, 'result': dict, 'usage_data': dict,
         'resource_ref_id': str, 'task_id': str, 'status': 'SUCCEEDED'}
    """
    env = ServerEnv()
    llm, err = await _resolve_llm(resource_ref_id)
    if err:
        return {'success': False, 'message': err, 'status': 'FAILED'}

    # Get full llm info (with uapi) for API call
    full_llm = await get_llm(llm.id)
    if not full_llm:
        return {'success': False, 'message': '模型API配置不完整', 'status': 'FAILED'}

    from uapi.appapi import UAPI

    # Get API user
    userid = await env.uapi_data.get_calluserid(full_llm.upappid, orgid=full_llm.ownerid)

    luid = getID()
    params_kw = DictObject(**request_data)
    params_kw.model = full_llm.model
    if not params_kw.get('transno'):
        params_kw.transno = luid

    try:
        if full_llm.stream == 'async':
            from .asyncinference import async_uapi_request_product
            result = await async_uapi_request_product(
                full_llm, userid, user_id, user_org_id, params_kw, luid)
            return result

        elif not full_llm.stream:
            from .syncinference import sync_uapi_request_product
            result = await sync_uapi_request_product(
                full_llm, userid, user_id, user_org_id, params_kw, luid)
            return result
        else:
            result = await _collect_stream(full_llm, userid, user_id,
                                           user_org_id, params_kw, luid)
            return result

    except Exception as e:
        exception(f'execute_product_service error: {e}')
        return {'success': False, 'message': str(e), 'status': 'FAILED',
                'task_id': luid}


async def _collect_stream(llm, api_userid, user_id, user_org_id, params_kw, luid):
    """Collect streaming response into a single result dict."""
    env = ServerEnv()
    from uapi.appapi import UAPI
    uapi = UAPI(llm.upappid, llm.apiname)

    outlines = []
    txt = ''
    usage = None
    start_timestamp = time.time()
    responsed_seconds = None

    try:
        first = True
        async for l in uapi.stream_linify(llm.upappid, llm.apiname,
                                           api_userid, params=params_kw):
            if first:
                first = False
                responsed_seconds = time.time() - start_timestamp
            if isinstance(l, bytes):
                l = l.decode('utf-8')
            if l and l[-1] == '\n':
                l = l[:-1]
            l = ''.join(l.split('\n'))
            if l and l != '[DONE]':
                try:
                    d = json.loads(l)
                except:
                    continue
                if d.get('reasoning_content'):
                    txt += d.get('reasoning_content')
                if d.get('content'):
                    txt += d['content']
                if d.get('usage'):
                    usage = d['usage']
                outlines.append(d)

        finish_seconds = time.time() - start_timestamp
        if responsed_seconds is None:
            responsed_seconds = finish_seconds

        # Write llmusage
        llmusage = DictObject()
        llmusage.id = luid
        llmusage.llmid = llm.id
        llmusage.use_date = curDateString()
        llmusage.use_time = timestampstr()
        llmusage.userid = user_id
        llmusage.usages = json.dumps(usage, ensure_ascii=False, indent=4) if usage else '{}'
        ioinfo = {"input": dict(params_kw), "output": outlines}
        webpath = await write_llmio(luid, ioinfo)
        llmusage.ioinfo = webpath
        llmusage.transno = params_kw.get('transno', luid)
        llmusage.responsed_seconds = responsed_seconds
        llmusage.finish_seconds = finish_seconds
        llmusage.status = 'SUCCEEDED'
        llmusage.userorgid = user_org_id
		llmusage.tenantid = params_kw.get('tenantid', params_kw.get('tentantid'))
        llmusage.ownerid = llm.ownerid
        llmusage.accounting_status = 'created'
        await write_llmusage(llmusage)

        return {
            'success': True,
            'result': {'content': txt, 'chunks': outlines},
            'usage_data': usage or {},
            'resource_ref_id': llm.id,
            'task_id': luid,
            'status': 'SUCCEEDED',
        }

    except Exception as e:
        exception(f'stream collect error: {e}')
        return {'success': False, 'message': str(e),
                'task_id': luid, 'status': 'FAILED'}


async def execute_product_service_stream(resource_ref_id, user_id, user_org_id, request_data):
    """执行大模型API调用（流式），返回异步生成器。

    Yields: {'chunk': dict, 'usage_data': dict|None, 'done': bool}
    Final chunk has done=True with complete usage_data.
    """
    llm, err = await _resolve_llm(resource_ref_id)
    if err:
        yield {'chunk': None, 'usage_data': None, 'done': True,
               'error': err}
        return

    full_llm = await get_llm(llm.id)
    if not full_llm:
        yield {'chunk': None, 'usage_data': None, 'done': True,
               'error': '模型API配置不完整'}
        return

    env = ServerEnv()
    from uapi.appapi import UAPI
    uapi = UAPI(full_llm.upappid, full_llm.apiname)
    api_userid = await env.uapi_data.get_calluserid(
        full_llm.upappid, orgid=full_llm.ownerid)

    params_kw = DictObject(**request_data)
    params_kw.model = full_llm.model
    luid = getID()
    if not params_kw.get('transno'):
        params_kw.transno = luid

    outlines = []
    txt = ''
    usage = None
    start_timestamp = time.time()
    responsed_seconds = None

    try:
        first = True
        async for l in uapi.stream_linify(full_llm.upappid, full_llm.apiname,
                                           api_userid, params=params_kw):
            if first:
                first = False
                responsed_seconds = time.time() - start_timestamp
            if isinstance(l, bytes):
                l = l.decode('utf-8')
            if l and l[-1] == '\n':
                l = l[:-1]
            l = ''.join(l.split('\n'))
            if l and l != '[DONE]':
                try:
                    d = json.loads(l)
                except:
                    continue
                if d.get('reasoning_content'):
                    txt += d.get('reasoning_content')
                if d.get('content'):
                    txt += d['content']
                if d.get('usage'):
                    usage = d['usage']
                outlines.append(d)
                d['llmusageid'] = luid
                yield {'chunk': d, 'usage_data': None, 'done': False}

        # Stream done — write llmusage
        finish_seconds = time.time() - start_timestamp
        if responsed_seconds is None:
            responsed_seconds = finish_seconds

        llmusage = DictObject()
        llmusage.id = luid
        llmusage.llmid = full_llm.id
        llmusage.use_date = curDateString()
        llmusage.use_time = timestampstr()
        llmusage.userid = user_id
        llmusage.usages = json.dumps(usage, ensure_ascii=False, indent=4) if usage else '{}'
        ioinfo = {"input": dict(params_kw), "output": outlines}
        webpath = await write_llmio(luid, ioinfo)
        llmusage.ioinfo = webpath
        llmusage.transno = params_kw.get('transno', luid)
        llmusage.responsed_seconds = responsed_seconds
        llmusage.finish_seconds = finish_seconds
        llmusage.status = 'SUCCEEDED'
        llmusage.userorgid = user_org_id
		llmusage.tenantid = params_kw.get('tenantid', params_kw.get('tentantid'))
        llmusage.ownerid = full_llm.ownerid
        llmusage.accounting_status = 'created'
        await write_llmusage(llmusage)

        yield {
            'chunk': None,
            'usage_data': usage or {},
            'done': True,
            'task_id': luid,
            'status': 'SUCCEEDED',
        }

    except Exception as e:
        exception(f'stream error: {e}')
        yield {'chunk': None, 'usage_data': None, 'done': True,
               'error': str(e), 'task_id': luid, 'status': 'FAILED'}


async def calculate_product_cost(resource_ref_id, usage_data, user_org_id=None):
    """计算本次消费的费用。

    Args:
        resource_ref_id: 资源模块内部ID（= llm.id）
        usage_data: dict, 用量数据 (prompt_tokens, completion_tokens 等)
        user_org_id: 用户组织ID（用于折扣）

    Returns:
        {'success': True, 'amount': float, 'original_amount': float,
         'cost': float, 'discount': float, 'pricing_program_id': str}
    """
    llm, err = await _resolve_llm(resource_ref_id)
    if err:
        return {'success': False, 'message': err}

    if not llm.ppid:
        return {'success': False, 'message': '无定价方案(ppid为空)'}

    env = ServerEnv()
    try:
        prices = await env.buffered_charging(llm.ppid, usage_data)
        if prices is None:
            return {'success': False,
                    'message': f'定价计算返回空(ppid={llm.ppid})'}

        amount = 0
        cost = 0
        for p in prices:
            amount += p.amount
            if p.cost:
                cost += p.cost

        # Apply customer discount
        discount = 1.0
        if user_org_id:
            try:
                discount = await env.get_customer_discount(
                    llm.ownerid, user_org_id)
            except:
                pass

        return {
            'success': True,
            'original_amount': round(amount, 6),
            'amount': round(amount * discount, 6),
            'cost': round(cost, 6),
            'discount': discount,
            'pricing_program_id': llm.ppid,
        }

    except Exception as e:
        exception(f'calculate_product_cost error: {e}')
        return {'success': False, 'message': f'定价计算失败: {e}'}
