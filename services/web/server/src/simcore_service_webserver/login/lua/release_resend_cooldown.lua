-- Releases the cooldown only while this request still owns it, so a failed
-- send cannot delete a window a later request armed.
--
-- KEYS[1] cooldown key, ARGV[1] the token this request wrote
if redis.call("GET", KEYS[1]) == ARGV[1] then
	return redis.call("DEL", KEYS[1])
end
return 0
