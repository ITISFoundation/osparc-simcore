-- Atomically release a distributed semaphore
-- KEYS[1]: semaphore_key (ZSET storing holders with timestamps)
-- KEYS[2]: holder_key (individual holder TTL key)
-- ARGV[1]: instance_id
-- ARGV[2]: ttl_seconds
--
-- Returns: {success, status, current_count, expired_count}
--   exit_code: 0 if released, 255 if failed
--   status: 'released', 'not_held', or 'already_expired'
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
    return {0, 'not_held', current_count, expired_count}
end

-- Step 3: Remove the semaphore entry and holder key
local removed_from_zset = redis.call('ZREM', semaphore_key, instance_id)
local removed_holder = redis.call('DEL', holder_key)

local current_count = redis.call('ZCARD', semaphore_key)

if removed_from_zset == 1 then
    return {0, 'released', current_count, expired_count}
else
    -- This shouldn't happen since we checked ZSCORE above, but handle it
    return {255, 'already_expired', current_count, expired_count}
end
