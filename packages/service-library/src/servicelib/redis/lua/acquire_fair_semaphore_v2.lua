-- Fair distributed semaphore using token pool (BRPOP-based)
-- KEYS[1]: tokens_key (LIST of available tokens)
-- KEYS[2]: holders_key (SET of current holder instance IDs)

-- ARGV[1]: instance_id
-- ARGV[2]: capacity (max concurrent holders)
-- ARGV[3]: ttl_seconds
--
-- Returns: {exit_code, status, token, current_count}
-- exit_code: 0 if acquired, 255 if timeout/failed
-- status: 'acquired' or 'timeout'

local holders_key = KEYS[1]
local holder_key = KEYS[2]

local token = ARGV[1]
local instance_id = ARGV[2]
local ttl_seconds = tonumber(ARGV[3])



-- Step 1: Register as holder
redis.call('SADD', holders_key, instance_id)
redis.call('SETEX', holder_key, ttl_seconds, token)

-- Step 2: Set expiry on holders set to prevent infinite growth
redis.call('EXPIRE', holders_key, ttl_seconds * 10)

local current_count = redis.call('SCARD', holders_key)

return {0, 'acquired', token, current_count}
