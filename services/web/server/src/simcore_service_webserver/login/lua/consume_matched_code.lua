-- Deletes the code and reports whether it did, so the caller grants access only
-- to the request that actually consumed the code. A replacement is never
-- destroyed, and the counter belongs to one generation and is always safe to
-- delete.
--
-- KEYS[1] code key, KEYS[2] trial-counter key, ARGV[1] the matched stored value
-- returns {1} consumed here, {0} replaced or already used
if redis.call("GET", KEYS[1]) == ARGV[1] then
	redis.call("DEL", KEYS[1])
	redis.call("DEL", KEYS[2])
	return 1
end
redis.call("DEL", KEYS[2])
return 0
