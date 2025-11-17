-- Check if the has_key exists before setting the arguments exists
-- KEYS[1]: has_key (HASH where all the )
--
-- ARGV[1]: a unique key
-- ARGV[2]: value of key 1
-- ARGV[n]: another unique key
-- ARGV[n+1]: value of the key n+1
--
-- Returns: the number of affected keys

if redis.call('exists', KEYS[1]) == 1 then
    -- If it exists, set multiple field-value pairs from ARGV using HSET and unpack
    -- ARGV should be a flat list: field1, value1, field2, value2, ...
    return redis.call('hset', KEYS[1], unpack(ARGV))
else
    -- If it does not exist, return 0 to indicate nothing was updated
    return 0
end
