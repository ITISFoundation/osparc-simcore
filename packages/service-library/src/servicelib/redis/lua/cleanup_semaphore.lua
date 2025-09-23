-- Cleanup orphaned tokens from crashed clients
-- KEYS[1]: tokens_key (LIST of available tokens)
-- KEYS[2]: holders_key (SET of current holders)
-- KEYS[3]: holder_prefix (prefix for holder keys, e.g. "semaphores:holders:key:")
-- ARGV[1]: capacity (total semaphore capacity)
--
-- Returns: {recovered_tokens, missing_tokens, excess_tokens}
-- This script should be run periodically to recover tokens from crashed clients

local tokens_key = KEYS[1]
local holders_key = KEYS[2]
local holder_prefix = KEYS[3]

local capacity = tonumber(ARGV[1])

-- Step 1: Get all current holders
local current_holders = redis.call('SMEMBERS', holders_key)
local recovered_tokens = 0
local cleaned_holders = {}

-- Step 2: Check each holder to see if their TTL key still exists
for i = 1, #current_holders do
    local holder_id = current_holders[i]
    local holder_key = holder_prefix .. holder_id
    local exists = redis.call('EXISTS', holder_key)

    if exists == 0 then
        -- Holder key doesn't exist but holder is in SET
        -- This indicates a crashed client - clean up and recover token
        redis.call('SREM', holders_key, holder_id)
        redis.call('LPUSH', tokens_key, 'token_recovered_' .. holder_id)
        recovered_tokens = recovered_tokens + 1
        table.insert(cleaned_holders, holder_id)
    end
end

-- Step 3: Ensure we have the correct total number of tokens
local remaining_holders = redis.call('SCARD', holders_key)
local available_tokens_count = redis.call('LLEN', tokens_key)
local total_tokens = remaining_holders + available_tokens_count

-- If we're missing tokens (due to crashes or Redis issues), add them back
local missing_tokens = capacity - total_tokens
for i = 1, missing_tokens do
    redis.call('LPUSH', tokens_key, 'token_missing_' .. i)
    recovered_tokens = recovered_tokens + 1
end

-- If we somehow have too many tokens (shouldn't happen), remove extras
local excess_tokens = total_tokens - capacity
for i = 1, excess_tokens do
    redis.call('RPOP', tokens_key)
end


return {recovered_tokens, missing_tokens, excess_tokens}
