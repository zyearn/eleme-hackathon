
--local time_last_update = tonumber(KEYS[1], 10)
--local records_kind = redis.call('zrangebyscore', 'food:stock:kind', time_last_update, "+inf")
--local records_count = redis.call('zrangebyscore', 'food:stock:count', time_last_update, "+inf")

--local stocks = {}
--for i = 1, #records_kind, 1 do
--        stocks[ tonumber(records_kind[i]) % 10000000 ] = tonumber(records_count[i]) % 10000000
--end

--local time_latest = tonumber(redis.call('get', 'timestamp'))

--local n = 3
--ret[1] = 'time_latest'
--ret[2] = time_latest
--for k, v in pairs(stocks) do
--    ret[n] = k
--    ret[n+1] = v
--    n = n + 2
--end
local ret = {}

local n  = 1
local records_order_cart = redis.call('hgetall', 'order:cart')
for i = 1, #records_order_cart, 2 do
    ret[n] = {}
    ret[n][1] = records_order_cart[i]
    ret[n][2] = redis.call('get', 'order:'..records_order_cart[i]..':user')
    ret[n][3] = redis.call('hgetall', 'cart:'..records_order_cart[i+1])
    n = n+1
end

return ret
