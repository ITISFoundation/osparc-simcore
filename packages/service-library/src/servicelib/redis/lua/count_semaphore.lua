-- Atomically count current semaphore holders (with cleanup)
-- KEYS[1]: semaphore_key (ZSET storing holders with timestamps)
-- ARGV[1]: ttl_seconds
--
-- Returns: {current_count, expired_count}
--   current_count: number of active holders after cleanup
--   expired_count: number of expired entries cleaned up

local semaphore_key = KEYS[1]
local ttl_seconds = tonumber(ARGV[1])

-- Get current Redis server time
local time_result = redis.call('TIME')
local current_time = tonumber(time_result[1]) + (tonumber(time_result[2]) / 1000000)

-- Step 1: Clean up expired entries
local expiry_threshold = current_time - ttl_seconds
local expired_count = redis.call('ZREMRANGEBYSCORE', semaphore_key, '-inf', expiry_threshold)

-- Step 2: Count remaining entries
local current_count = redis.call('ZCARD', semaphore_key)

return {current_count, expired_count}
