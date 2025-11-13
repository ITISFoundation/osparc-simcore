-- Check if the key (hash) given in KEYS[1] exists
if redis.call('exists', KEYS[1]) == 1 then
    -- If it exists, set multiple field-value pairs from ARGV using HSET and unpack
    -- ARGV should be a flat list: field1, value1, field2, value2, ...
    return redis.call('hset', KEYS[1], unpack(ARGV))
else
    -- If it does not exist, return 0 to indicate nothing was updated
    return 0
end
