-- KEYS[1]: time_last_update

-- 123456689     012     3456
--    time   | food_id | stock
-- 864000000     100     1000   = 10 days <
-- 900719925     474     0992   = 2^53

local time_last_update = tonumber(KEYS[1], 10)
local time_latest = tonumber(redis.call('get', 'timestamp'))
local ret = {}
ret[1] = 'time_latest'
ret[2] = time_latest

if time_last_update == time_latest then
    return ret
end

local records_kind = redis.call('zrangebyscore', 'food:stock:kind', time_last_update, "+inf")
local records_count = redis.call('zrangebyscore', 'food:stock:count', time_last_update, "+inf")

local stocks = {}
for i = 1, #records_kind, 1 do
        stocks[ tonumber(records_kind[i]) % 10000000 ] = tonumber(records_count[i]) % 10000000
end


local n = 3

for k, v in pairs(stocks) do
    ret[n] = k
    ret[n+1] = v
    n = n + 2
end

return ret
