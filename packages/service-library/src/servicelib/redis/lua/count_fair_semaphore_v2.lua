-- Count current semaphore holders (simplified for token pool design)
-- KEYS[1]: holders_key (SET of current holders)
-- KEYS[2]: tokens_key (LIST of available tokens)
-- ARGV[1]: capacity (total semaphore capacity)
--
-- Returns: {current_holders, available_tokens, total_capacity}

local holders_key = KEYS[1]
local tokens_key = KEYS[2]

local capacity = tonumber(ARGV[1])

-- Count current holders and available tokens
local current_holders = redis.call('SCARD', holders_key)
local available_tokens = redis.call('LLEN', tokens_key)

return {current_holders, available_tokens, capacity}
