-- Release fair semaphore and return token to pool
-- KEYS[1]: tokens_key (LIST of available tokens)
-- KEYS[2]: holders_key (SET of current holders)
-- KEYS[3]: holder_key (individual holder TTL key for this instance)
-- ARGV[1]: instance_id
--
-- Returns: {exit_code, status, current_count}
-- exit_code: 0 if released, 255 if failed
-- status: 'released', 'not_held', or 'already_expired'

local tokens_key = KEYS[1]
local holders_key = KEYS[2]
local holder_key = KEYS[3]

local instance_id = ARGV[1]

-- Step 1: Check if this instance is currently a holder
local is_holder = redis.call('SISMEMBER', holders_key, instance_id)
if is_holder == 0 then
    -- Not in holders set - check if holder key exists
    local exists = redis.call('EXISTS', holder_key)
    if exists == 1 then
        -- Holder key exists but not in set - clean it up
        redis.call('DEL', holder_key)
        return {255, 'already_expired', redis.call('SCARD', holders_key)}
    else
        return {255, 'not_held', redis.call('SCARD', holders_key)}
    end
end

-- Step 2: Get the token from holder key before releasing
local token = redis.call('GET', holder_key)
if not token then
    -- Fallback token if somehow missing
    token = 'token_default'
end

-- Step 3: Release the semaphore
redis.call('SREM', holders_key, instance_id)
redis.call('DEL', holder_key)

-- Step 4: Return token to available pool
-- This automatically unblocks any waiting BRPOP calls
redis.call('LPUSH', tokens_key, token)

local new_count = redis.call('SCARD', holders_key)

return {0, 'released', new_count}
