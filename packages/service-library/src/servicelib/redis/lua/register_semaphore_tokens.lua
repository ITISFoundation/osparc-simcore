-- Simple token initialization and management for Python BRPOP
-- KEYS[1]: tokens_key (LIST of available tokens)
-- KEYS[2]: holders_key (SET of current holder instance IDs)

-- ARGV[1]: capacity (max concurrent holders)
-- ARGV[2]: ttl_seconds
--
-- Returns: {exit_code}
-- exit_code: 0 if registered successfully

local tokens_key = KEYS[1]
local holders_key = KEYS[2]

local capacity = tonumber(ARGV[1])
local ttl_seconds = tonumber(ARGV[2])

-- Use a persistent marker to track if semaphore was ever initialized
local init_marker_key = tokens_key .. ':initialized'

-- Check if we've ever initialized this semaphore
local was_initialized = redis.call('EXISTS', init_marker_key)

if was_initialized == 0 then
    -- First time initialization - set the permanent marker
    redis.call('SET', init_marker_key, '1')
    redis.call('EXPIRE', init_marker_key, ttl_seconds)

    -- Initialize with capacity number of tokens
    for i = 1, capacity do
        redis.call('LPUSH', tokens_key, 'token_' .. i)
    end
    -- Set expiry on tokens list
    redis.call('EXPIRE', tokens_key, ttl_seconds)
    return {0, 'initialized'}
end


return {0, 'already_initialized'}
