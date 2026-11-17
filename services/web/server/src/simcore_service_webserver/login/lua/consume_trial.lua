-- Charges one trial and returns the stored value atomically, so a trial is only
-- ever charged to the generation whose digest is then compared. INCR and PEXPIRE
-- are in the same script, and the lifetime is copied from the code with
-- PTTL/PEXPIRE, so a counter expires with its code to the millisecond and can
-- never elapse early only to be recreated and refill the budget of a live code.
--
-- KEYS[1] code key, KEYS[2] trial-counter prefix
-- ARGV[1] max trials, ARGV[2] stored-value length, ARGV[3] generation length
-- returns {0} no code, {1} budget spent, {2, stored value} trial charged
local stored = redis.call("GET", KEYS[1])
if not stored or #stored ~= tonumber(ARGV[2]) then
	return { 0 }
end
local counter_key = KEYS[2] .. string.sub(stored, 1, tonumber(ARGV[3]))
local trials = redis.call("INCR", counter_key)
if trials == 1 then
	local pttl = redis.call("PTTL", KEYS[1])
	if pttl < 1 then
		pttl = 1
	end
	redis.call("PEXPIRE", counter_key, pttl)
end
if trials > tonumber(ARGV[1]) then
	return { 1 }
end
return { 2, stored }
