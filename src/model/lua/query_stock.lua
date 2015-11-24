-- KEYS[1]: time_last_update

local time_last_update = tonumber(KEYS[1], 10)
local time_latest = tonumber(redis.call('get', 'timestamp'))
local ret = {}
ret[1] = 'time_latest'
ret[2] = time_latest

if time_last_update == time_latest then
    return ret
end
local records = redis.call('zrangebyscore', 'food:id:stock', time_last_update, "+inf")

local stocks = {}
for i = 1, #records, 1 do
    local nb = tonumber(records[i])
    stocks[ tonumber(nb / 10000) % 100000 ] = nb % 10000
end


local n = 3

for k, v in pairs(stocks) do
    ret[n] = k
    ret[n+1] = v
    n = n + 2
end

return ret
