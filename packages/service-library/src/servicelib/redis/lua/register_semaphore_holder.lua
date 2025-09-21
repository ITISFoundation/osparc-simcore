-- Simple token initialization and management for Python BRPOP
-- KEYS[1]: tokens_key (LIST of available tokens)
-- KEYS[2]: holders_key (SET of current holder instance IDs)
-- KEYS[3]: holder_key (individual holder TTL key for this instance)
-- ARGV[1]: instance_id
-- ARGV[2]: capacity (max concurrent holders)
-- ARGV[3]: ttl_seconds
-- ARGV[4]: token (the token received from BRPOP)
--
-- Returns: {exit_code, status, current_count}
-- exit_code: 0 if registered successfully

local tokens_key = KEYS[1]
local holders_key = KEYS[2]

local capacity = tonumber(ARGV[1])
local ttl_seconds = tonumber(ARGV[2])

-- Step 1: Initialize token pool if needed (first time setup)
local tokens_exist = redis.call('EXISTS', tokens_key)
local holders_exist = redis.call('EXISTS', holders_key)
if tokens_exist == 0 and holders_exist == 0 then
    -- Initialize with capacity number of tokens
    for i = 1, capacity do
        redis.call('LPUSH', tokens_key, 'token_' .. i)
    end
    -- Set expiry on tokens list to prevent infinite growth
    -- redis.call('EXPIRE', tokens_key, ttl_seconds)
end

return 0
