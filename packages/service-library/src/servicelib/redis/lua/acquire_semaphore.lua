-- Atomically acquire a distributed semaphore
-- KEYS[1]: semaphore_key (ZSET storing holders with timestamps)
-- KEYS[2]: holder_key (individual holder TTL key)
-- ARGV[1]: instance_id
-- ARGV[2]: capacity (max concurrent holders)
-- ARGV[3]: ttl_seconds
--
-- Returns: {success, status, current_count, expired_count}
--   success: 1 if acquired, 0 if failed
--   status: 'acquired' or 'capacity_full'
--   current_count: number of holders after operation
--   expired_count: number of expired entries cleaned up

local semaphore_key = KEYS[1]
local holder_key = KEYS[2]
local instance_id = ARGV[1]
local capacity = tonumber(ARGV[2])
local ttl_seconds = tonumber(ARGV[3])

-- Get current Redis server time
local time_result = redis.call('TIME')
local current_time = tonumber(time_result[1]) + (tonumber(time_result[2]) / 1000000)

-- Step 1: Clean up expired entries
local expiry_threshold = current_time - ttl_seconds
local expired_count = redis.call('ZREMRANGEBYSCORE', semaphore_key, '-inf', expiry_threshold)

-- Step 2: Check current capacity after cleanup
local current_count = redis.call('ZCARD', semaphore_key)

-- Step 3: Try to acquire if under capacity
if current_count < capacity then
    -- Atomically add to semaphore and set holder key
    redis.call('ZADD', semaphore_key, current_time, instance_id)
    redis.call('SETEX', holder_key, ttl_seconds, '1')

    return {1, 'acquired', current_count + 1, expired_count}
else
    return {0, 'capacity_full', current_count, expired_count}
end
