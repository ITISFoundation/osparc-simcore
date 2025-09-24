-- Renew semaphore holder TTL (simplified for token pool design)
-- KEYS[1]: holders_key (SET of current holders)
-- KEYS[2]: holder_key (individual holder TTL key for this instance)
-- KEYS[3]: tokens_key (LIST of available tokens)
-- ARGV[1]: instance_id
-- ARGV[2]: ttl_seconds
-- ARGV[3]: holders_ttl_seconds (to renew holders set)
-- ARGV[4]: tokens_ttl_seconds (to renew tokens list)
--
-- Returns: {exit_code, status, current_count}
-- exit_code: 0 if renewed, 255 if failed
-- status: 'renewed', 'not_held', or 'expired'

local holders_key = KEYS[1]
local holder_key = KEYS[2]
local tokens_key = KEYS[3]

local instance_id = ARGV[1]
local ttl_seconds = tonumber(ARGV[2])
local holders_ttl_seconds = tonumber(ARGV[3])
local tokens_ttl_seconds = tonumber(ARGV[4])

-- Step 1: Check if this instance is currently a holder
local is_holder = redis.call('SISMEMBER', holders_key, instance_id)
if is_holder == 0 then
    -- Not in holders set
    return {255, 'not_held', redis.call('SCARD', holders_key)}
end

-- Step 2: Check if holder key exists (to detect if it expired)
local exists = redis.call('EXISTS', holder_key)
if exists == 0 then
    -- Holder key expired
    return {255, 'expired', redis.call('SCARD', holders_key)}
end

-- Step 3: Renew the holder key TTL
local token = redis.call('GET', holder_key)
redis.call('SETEX', holder_key, ttl_seconds, token)

-- Step 4: Renew the holders set and tokens list TTLs to prevent infinite growth
redis.call('EXPIRE', holders_key, holders_ttl_seconds)
redis.call('EXPIRE', tokens_key, tokens_ttl_seconds)
local init_marker_tokens_key = tokens_key .. ':initialized'
redis.call('EXPIRE', init_marker_tokens_key, tokens_ttl_seconds)

return {0, 'renewed', redis.call('SCARD', holders_key)}
