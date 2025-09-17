-- Atomically renew a distributed semaphore holder's TTL
-- KEYS[1]: semaphore_key (ZSET storing holders with timestamps)
-- KEYS[2]: holder_key (individual holder TTL key)
-- ARGV[1]: instance_id
-- ARGV[2]: ttl_seconds
--
-- Returns: {success, status, current_count, expired_count}
--   exit_code: 0 if renewed, 255 if failed
--   status: 'renewed', 'not_held', or 'expired'
--   current_count: number of holders after operation
--   expired_count: number of expired entries cleaned up

local semaphore_key = KEYS[1]
local holder_key = KEYS[2]
local instance_id = ARGV[1]
local ttl_seconds = tonumber(ARGV[2])

-- Get current Redis server time
local time_result = redis.call('TIME')
local current_time = tonumber(time_result[1]) + (tonumber(time_result[2]) / 1000000)

-- Step 1: Clean up expired entries
local expiry_threshold = current_time - ttl_seconds
local expired_count = redis.call('ZREMRANGEBYSCORE', semaphore_key, '-inf', expiry_threshold)

-- Step 2: Check if this instance currently holds the semaphore
local score = redis.call('ZSCORE', semaphore_key, instance_id)

if score == false then
    -- Instance doesn't hold the semaphore
    local current_count = redis.call('ZCARD', semaphore_key)
    return {255, 'not_held', current_count, expired_count}
end

-- Step 3: Check if the holder key still exists (not expired)
local exists = redis.call('EXISTS', holder_key)
if exists == 0 then
    -- Holder key expired, remove from semaphore and fail renewal
    redis.call('ZREM', semaphore_key, instance_id)
    local current_count = redis.call('ZCARD', semaphore_key)
    return {255, 'expired', current_count, expired_count + 1}
end

-- Step 4: Renew both the semaphore entry and holder key
redis.call('ZADD', semaphore_key, current_time, instance_id)
redis.call('SETEX', holder_key, ttl_seconds, '1')

local current_count = redis.call('ZCARD', semaphore_key)
return {0, 'renewed', current_count, expired_count}
