"""
Redis atomic balance reservation for llmage.
Prevents concurrent overspend: pre-deduct before inference, settle after accounting.

Uses a module-level redis.asyncio singleton so the atomic reserve works in
EVERY process (web workers + backend_accounting) without needing env.redis
to be injected. This fixes the previous fatal issue where env.redis was never
set, so reserve always silently fell back to the non-atomic DB check.

Key patterns:
  balance:{userorgid}           — current pre-deducted balance (int, cents)
  reserve:{luid}                — {userorgid}|{llmid}|{max_cost}  (TTL)
  model:max_cost:{llmid}        — historical max actual customer charge (int, cents)

Reserve TTL: 600s for fast (stream/sync) calls, 3600s for async tasks that
may run for minutes before finalize/refund.
"""
import asyncio
from appPublic.log import debug, exception

# ── Module-level async Redis singleton ───────────────────────
_redis = None
_redis_lock = asyncio.Lock()


def _redis_url():
    try:
        from appPublic.jsonConfig import getConfig
        config = getConfig()
        url = getattr(config.website, 'session_redis', None)
        if url:
            u = getattr(url, 'url', None)
            if u:
                return u
    except Exception:
        pass
    return "redis://127.0.0.1:6379"


async def _get_redis():
    """Return a shared redis.asyncio client (lazy singleton)."""
    global _redis
    if _redis is not None:
        return _redis
    async with _redis_lock:
        if _redis is None:
            import redis.asyncio as aioredis
            _redis = await aioredis.from_url(
                _redis_url(), decode_responses=True)
    return _redis


# ── Lua scripts ──────────────────────────────────────────────

RESERVE_LUA = """
local bal_key = KEYS[1]
local cost_key = KEYS[2]
local reserve_key = KEYS[3]
local max_cost = tonumber(ARGV[1])
local db_balance = tonumber(ARGV[2])    -- 0 means no DB fallback
local reserve_val = ARGV[3]
local ttl = tonumber(ARGV[4])

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
redis.call('SETEX', reserve_key, ttl, reserve_val)
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


async def _update_max_cost(llmid, actual_cost):
    """Bump model:max_cost if actual exceeds stored value; persist to DB.

    Keeps the pre-deduct baseline growing even when the original reserve was
    skipped (no_history cold start) — otherwise reserve would never activate.
    """
    try:
        redis = await _get_redis()
        cost_key = f'model:max_cost:{llmid}'
        cost_cents = _cents(actual_cost)
        stored = await redis.get(cost_key)
        if stored and int(stored) >= cost_cents:
            return
        await redis.set(cost_key, cost_cents)
        from .utils import update_model_max_cost
        await update_model_max_cost(llmid, actual_cost)
    except Exception as e:
        debug(f'_update_max_cost failed: {e}')


async def reserve_balance(env, llmid, userorgid, luid, ttl=600, userid=None):
    """Atomically check balance and deduct max_cost via Redis Lua.

    Policy (centralized so every entry behaves the same):
      - Self-owned org (llm.ownerid == userorgid): skip reserve.
      - tpac user (external balance system): skip reserve.
      - No pricing (ppid empty): skip reserve (availability handled elsewhere).

    Returns:
      {'ok': True, 'max_cost': X}            — reserved X
      {'ok': True, 'max_cost': 0, 'skip': ...} — reserve skipped by policy
      {'ok': True, 'max_cost': 0, 'no_history': True} — no max_cost data yet
      {'ok': False, 'reason': ...}           — insufficient balance
      {'ok': True, 'max_cost': 0, 'no_redis': True} — Redis down, DB fallback
    """
    try:
        # ── Policy checks (need llm info) ──
        try:
            from .utils import get_llmage_llm, get_user_tpac
            llm = await get_llmage_llm(llmid)
            if llm and llm.ownerid == userorgid:
                return {'ok': True, 'max_cost': 0, 'skip': 'self_org'}
            if not llm or not llm.ppid:
                return {'ok': True, 'max_cost': 0, 'skip': 'no_ppid'}
            # tpac user: balance lives in external system, skip redis reserve
            if userid:
                try:
                    tpac = await get_user_tpac(userid)
                    if tpac:
                        return {'ok': True, 'max_cost': 0, 'skip': 'tpac'}
                except Exception as e:
                    debug(f'reserve_balance: tpac check failed: {e}')
        except Exception as e:
            debug(f'reserve_balance: policy check failed: {e}')

        redis = await _get_redis()
        bal_key = f'balance:{userorgid}'
        cost_key = f'model:max_cost:{llmid}'
        reserve_key = f'reserve:{luid}'

        # Load max_cost from Redis if cached, else from DB history
        max_cost = 0
        stored = await redis.get(cost_key)
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

        # Load balance from DB if not cached in Redis
        db_balance = 0
        stored_bal = await redis.get(bal_key)
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
        result = await redis.eval(RESERVE_LUA, 3,
            bal_key, cost_key, reserve_key,
            str(max_cost), str(db_balance), reserve_val, str(ttl))

        if result[0] == 0:
            return {'ok': False, 'reason': result[1]}
        return {'ok': True, 'max_cost': _from_cents(result[1])}

    except Exception as e:
        # Redis down or unreachable — fall back to DB check, don't block
        debug(f'reserve_balance: Redis error, falling back to DB: {e}')
        return {'ok': True, 'max_cost': 0, 'no_redis': True}


async def finalize_balance(env, luid, actual_cost, llmid=None):
    """After accounting: adjust balance, update max_cost.

    llmid: needed for cold-start max_cost updates when no reserve existed
    (reserve skipped due to no_history) — keeps the pre-deduct baseline
    growing so future calls can reserve.
    """
    try:
        redis = await _get_redis()
        reserve_key = f'reserve:{luid}'

        reserve_val = await redis.get(reserve_key)
        if not reserve_val:
            debug(f'finalize_balance: no reserve for luid={luid}')
            if llmid:
                await _update_max_cost(llmid, actual_cost)
            return

        # Parse to get llmid (reserve_val: userorgid|llmid|max_cost)
        parts = reserve_val.split('|')
        if len(parts) < 3:
            return
        llmid = parts[1]
        cost_key = f'model:max_cost:{llmid}'

        result = await redis.eval(FINALIZE_LUA, 2,
            cost_key, reserve_key, str(_cents(actual_cost)))

        if result[0] == 0:
            debug(f'finalize_balance: {result[1]}')
            return

        max_c = _from_cents(result[2])
        diff = _from_cents(result[4])
        debug(f'finalize_balance: luid={luid} max={max_c} actual={actual_cost} diff={diff}')

        # Persist max_cost to DB if actual exceeded previous max
        if actual_cost > max_c:
            await _update_max_cost(llmid, actual_cost)

    except Exception as e:
        exception(f'finalize_balance error: {e}')


async def refund_balance(env, luid):
    """Full refund on API failure."""
    try:
        redis = await _get_redis()
        reserve_key = f'reserve:{luid}'
        result = await redis.eval(REFUND_LUA, 1, reserve_key)
        if result[0] == 1:
            debug(f'refund_balance: luid={luid} refund={_from_cents(result[1])}')
        else:
            debug(f'refund_balance: luid={luid} skipped ({result[1]})')
    except Exception as e:
        exception(f'refund_balance error: {e}')


async def extend_reserve(env, luid, ttl):
    """Extend TTL of an existing reserve.

    Used when an entry pre-reserved with the short (600s) TTL but the
    request is dispatched to async mode, where the task may run longer.
    """
    try:
        redis = await _get_redis()
        await redis.expire(f'reserve:{luid}', ttl)
    except Exception as e:
        debug(f'extend_reserve failed: {e}')


async def invalidate_balance_cache(userorgid):
    """Delete the cached Redis balance so the next reserve reloads from DB.

    Must be called after recharge / recharge reversal, otherwise the
    pre-deduct baseline stays stale and valid requests get rejected.
    """
    try:
        redis = await _get_redis()
        await redis.delete(f'balance:{userorgid}')
        debug(f'invalidate_balance_cache: balance:{userorgid} deleted')
    except Exception as e:
        debug(f'invalidate_balance_cache failed: {e}')
