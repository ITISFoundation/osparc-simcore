-- Fair distributed semaphore using token pool (BRPOP-based)
-- KEYS[1]: holders_key (SET of current holder instance IDs)
-- KEYS[2]: holder_key (individual holder TTL key for this instance)

-- ARGV[1]: token (the token received from BRPOP)
-- ARGV[2]: instance_id (the instance trying to acquire the semaphore)
-- ARGV[3]: ttl_seconds (for the holder_key)
-- ARGV[4]: holders_set_ttl_seconds (to set expiry on holders set)
--
-- Returns: {exit_code, status, token, current_count}
-- exit_code: 0 if acquired
-- status: 'acquired'

local holders_key = KEYS[1]
local holder_key = KEYS[2]

local token = ARGV[1]
local instance_id = ARGV[2]
local ttl_seconds = tonumber(ARGV[3])
local holders_set_ttl_seconds = tonumber(ARGV[4])



-- Step 1: Register as holder
redis.call('SADD', holders_key, instance_id)
redis.call('SETEX', holder_key, ttl_seconds, token)

-- Step 2: Set expiry on holders set to prevent infinite growth
redis.call('EXPIRE', holders_key, holders_set_ttl_seconds)

local current_count = redis.call('SCARD', holders_key)

return {0, 'acquired', token, current_count}
