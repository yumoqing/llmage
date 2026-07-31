"""
Redis atomic balance reservation for llmage.
Prevents concurrent overspend: pre-deduct before inference, settle after accounting.

Key patterns:
  balance:{userorgid}           — current pre-deducted balance (int, cents)
  reserve:{luid}                — {userorgid}|{llmid}|{max_cost}  (TTL 600s)
  model:max_cost:{llmid}        — historical max actual customer charge (int, cents)
"""
import asyncio
from appPublic.log import debug, exception

# ── Lua scripts ──────────────────────────────────────────────

RESERVE_LUA = """
local bal_key = KEYS[1]
local cost_key = KEYS[2]
local reserve_key = KEYS[3]
local max_cost = tonumber(ARGV[1])
local db_balance = tonumber(ARGV[2])    -- 0 means no DB fallback
local reserve_val = ARGV[3]

-- Get or init max_cost: use stored if higher, else set from arg
local stored_max = redis.call('GET', cost_key)
if stored_max then
    max_cost = math.max(max_cost, tonumber(stored_max))
elseif max_cost > 0 then
    redis.call('SET', cost_key, max_cost)
end
if max_cost <= 0 then
    return {0, 'max_cost is zero'}
end

-- Load or init balance
local balance = redis.call('GET', bal_key)
if not balance then
    if db_balance > 0 then
        balance = db_balance
        redis.call('SET', bal_key, db_balance)
    else
        return {0, 'balance not initialized'}
    end
end
balance = tonumber(balance)

-- Check and deduct
if balance < max_cost then
    return {0, 'insufficient balance'}
end
redis.call('DECRBY', bal_key, max_cost)
redis.call('SETEX', reserve_key, 600, reserve_val)
return {1, max_cost}
"""

FINALIZE_LUA = """
local cost_key = KEYS[1]
local reserve_key = KEYS[2]
local actual_cost = tonumber(ARGV[1])

-- Atomically pop reserve
local reserve_val = redis.call('GETDEL', reserve_key)
if not reserve_val then
    return {0, 'no reserve'}
end

-- Parse: userorgid|llmid|max_cost
local i = 1
local userorgid, llmid, max_cost
for part in string.gmatch(reserve_val, '([^|]+)') do
    if i == 1 then userorgid = part
    elseif i == 2 then llmid = part
    elseif i == 3 then max_cost = tonumber(part) end
    i = i + 1
end

-- Update max_cost if actual exceeds
if actual_cost > max_cost then
    redis.call('SET', cost_key, actual_cost)
    max_cost = actual_cost
end

-- Adjust balance
local bal_key = 'balance:' .. userorgid
local diff = max_cost - actual_cost
if diff > 0 then
    redis.call('INCRBY', bal_key, diff)
elseif diff < 0 then
    redis.call('DECRBY', bal_key, -diff)
end

return {1, userorgid, max_cost, actual_cost, diff}
"""

REFUND_LUA = """
local reserve_key = KEYS[1]

local reserve_val = redis.call('GETDEL', reserve_key)
if not reserve_val then
    return {0, 'no reserve'}
end

local i = 1
local userorgid, llmid, max_cost
for part in string.gmatch(reserve_val, '([^|]+)') do
    if i == 1 then userorgid = part
    elseif i == 2 then llmid = part
    elseif i == 3 then max_cost = tonumber(part) end
    i = i + 1
end

if max_cost > 0 then
    redis.call('INCRBY', 'balance:' .. userorgid, max_cost)
end
return {1, max_cost, userorgid}
"""


def _cents(f):
    return int(round(float(f) * 100))


def _from_cents(c):
    return round(int(c) / 100, 2)


async def _redis_eval(env, script, nkeys, *keys_and_args):
    """Eval Lua script via env's Redis connection."""
    if not hasattr(env, 'redis') or env.redis is None:
        raise RuntimeError('Redis unavailable')
    return await asyncio.to_thread(env.redis.eval, script, nkeys, *keys_and_args)


async def reserve_balance(env, llmid, userorgid, luid):
    """Atomically check balance and deduct max_cost via Redis Lua."""
    try:
        bal_key = f'balance:{userorgid}'
        cost_key = f'model:max_cost:{llmid}'
        reserve_key = f'reserve:{luid}'
        
        # Load max_cost from DB if not cached
        redis = env.redis
        max_cost = 0
        stored = await asyncio.to_thread(redis.get, cost_key)
        if stored:
            max_cost = int(stored)
        else:
            try:
                from .utils import get_model_max_cost
                mc = await get_model_max_cost(llmid)
                if mc and mc > 0:
                    max_cost = _cents(mc)
            except Exception as e:
                debug(f'reserve_balance: get_model_max_cost failed: {e}')
        
        if max_cost <= 0:
            return {'ok': True, 'max_cost': 0, 'no_history': True}
        
        # Load balance from DB if not cached
        db_balance = 0
        stored_bal = await asyncio.to_thread(redis.get, bal_key)
        if not stored_bal:
            try:
                from accounting.getaccount import getCustomerBalance
                from sqlor.dbpools import get_sor_context
                async with get_sor_context(env, 'accounting') as sor:
                    bal = await getCustomerBalance(sor, userorgid)
                    if bal is not None:
                        db_balance = _cents(float(bal))
            except Exception as e:
                debug(f'reserve_balance: getCustomerBalance failed: {e}')
        
        reserve_val = f'{userorgid}|{llmid}|{max_cost}'
        result = await _redis_eval(env, RESERVE_LUA, 3,
            bal_key, cost_key, reserve_key,
            str(max_cost), str(db_balance), reserve_val)
        
        if result[0] == 0:
            return {'ok': False, 'reason': result[1]}
        return {'ok': True, 'max_cost': _from_cents(result[1])}
    
    except RuntimeError:
        debug('reserve_balance: Redis unavailable, skip')
        return {'ok': True, 'max_cost': 0, 'no_redis': True}
    except Exception as e:
        exception(f'reserve_balance error: {e}')
        return {'ok': False, 'reason': str(e)}


async def finalize_balance(env, luid, actual_cost):
    """After accounting: adjust balance, update max_cost."""
    try:
        cost_key = 'model:max_cost:dummy'
        reserve_key = f'reserve:{luid}'
        
        # We need the llmid to get the correct cost_key, but we won't know it
        # until parsing the reserve. So use a placeholder and let Lua handle it.
        # Actually FINALIZE_LUA only uses cost_key for updating, so pass a dummy.
        # The real cost_key needs the llmid which comes from reserve parsing.
        
        redis = env.redis
        reserve_val = await asyncio.to_thread(redis.get, reserve_key)
        if not reserve_val:
            debug(f'finalize_balance: no reserve for luid={luid}')
            return
        
        # Parse to get llmid
        parts = reserve_val.split('|')
        if len(parts) < 3:
            return
        llmid = parts[1]
        cost_key = f'model:max_cost:{llmid}'
        
        result = await _redis_eval(env, FINALIZE_LUA, 2,
            cost_key, reserve_key, str(_cents(actual_cost)))
        
        if result[0] == 0:
            debug(f'finalize_balance: {result[1]}')
            return
        
        max_c = _from_cents(result[2])
        diff = _from_cents(result[4])
        debug(f'finalize_balance: luid={luid} max={max_c} actual={actual_cost} diff={diff}')
        
        # Persist max_cost to DB if actual exceeded previous max
        if actual_cost > max_c:
            try:
                from .utils import update_model_max_cost
                await update_model_max_cost(llmid, actual_cost)
            except Exception as e:
                debug(f'finalize_balance: DB persist failed: {e}')
    
    except RuntimeError:
        debug('finalize_balance: Redis unavailable, skip')
    except Exception as e:
        exception(f'finalize_balance error: {e}')


async def refund_balance(env, luid):
    """Full refund on API failure."""
    try:
        reserve_key = f'reserve:{luid}'
        result = await _redis_eval(env, REFUND_LUA, 1, reserve_key)
        if result[0] == 1:
            debug(f'refund_balance: luid={luid} refund={_from_cents(result[1])}')
        else:
            debug(f'refund_balance: luid={luid} skipped ({result[1]})')
    except RuntimeError:
        pass
    except Exception as e:
        exception(f'refund_balance error: {e}')
