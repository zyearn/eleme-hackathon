-- KEYS[1]: time_last_update

-- 123456689     012     3456
--    time   | food_id | stock
-- 864000000     100     1000   = 10 days <
-- 900719925     474     0992   = 2^53

local BASETIME = 1447587580

local time_last_update = tonumber(KEYS[1], 10)
local lef = time_last_update * 10000000
local rig = lef + 9999999
local records = redis.call('zrangebyscore', 'food:stock', lef, "+inf")

local stocks = {}
for i = 1, #records, 1 do
    local packed = tonumber(records[i])
    local id = packed / 10000 % 1000
    local stock = packed % 10000
    stocks[id] = stock
end

local latest = redis.call('ZREVRANGEBYSCORE', 'food:stock', '+inf', '-inf', 'WITHSCORES', 'LIMIT', '0', '1')
local time_latest = tonumber(latest[2]) / 10000000
local ret = {}
local n = 3
ret[1] = 'time_latest'
ret[2] = time_latest
for k, v in pairs(stocks) do
    ret[n] = k
    ret[n+1] = v
    n = n + 2
end

return ret