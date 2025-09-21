-- Renew semaphore holder TTL (simplified for token pool design)
-- KEYS[1]: holders_key (SET of current holders)
-- KEYS[2]: holder_key (individual holder TTL key for this instance)
-- ARGV[1]: instance_id
-- ARGV[2]: ttl_seconds
--
-- Returns: {exit_code, status, current_count}
-- exit_code: 0 if renewed, 255 if failed
-- status: 'renewed', 'not_held', or 'expired'

local holders_key = KEYS[1]
local holder_key = KEYS[2]

local instance_id = ARGV[1]
local ttl_seconds = tonumber(ARGV[2])

-- Step 1: Check if this instance is currently a holder
local is_holder = redis.call('SISMEMBER', holders_key, instance_id)
if is_holder == 0 then
    -- Not in holders set
    local current_count = redis.call('SCARD', holders_key)
    return {255, 'not_held', current_count}
end

-- Step 2: Check if holder key exists (to detect if it expired)
local exists = redis.call('EXISTS', holder_key)
if exists == 0 then
    -- Holder key expired - remove from set and fail renewal
    redis.call('SREM', holders_key, instance_id)
    local current_count = redis.call('SCARD', holders_key)
    return {255, 'expired', current_count}
end

-- Step 3: Renew the holder key TTL
local token = redis.call('GET', holder_key)
redis.call('SETEX', holder_key, ttl_seconds, token)

local current_count = redis.call('SCARD', holders_key)

return {0, 'renewed', current_count}
