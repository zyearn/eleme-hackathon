-- KEYS[1]: cart_id
-- KEYS[2]: order_id
-- KEYS[3]: access_token
-- 
-- return  0: OK
-- return -1: CART_NOT_FOUND
-- return -2: NOT_AUTHORIZED_TO_ACCESS_CART
-- return -3: FOOD_OUT_OF_STOCK
-- return -4: ORDER_OUT_OF_LIMIT
local belong_user = redis.call('get', 'cart:'..KEYS[1]..':user')
if not belong_user then
    return -1
end

local user_id = redis.call('get', 'token:'..KEYS[3]..':user')
if user_id ~= belong_user then
    return -2
end

local order_exist = redis.call('get', 'user:'..user_id..':order');
if order_exist then
    return -4
end

local tb = {}
local n = 1
local cart_items = redis.call('hgetall', 'cart:'..KEYS[1])
for i = 1, #cart_items, 2 do
    local id = tonumber(cart_items[i])
    local count = tonumber(cart_items[i+1])

    local time_last_update = redis.call('hget', 'food:last_update_time', id)
    local records = redis.call('zrangebyscore', 'food:id:stock', tonumber(time_last_update), tonumber(time_last_update))
    
    local stock
    if records[1] == nil then
        stock = 100
    else
        stock = tonumber(records[1]) % 10000
    end

    local remain = stock - count
    if remain < 0 then
            return -3
    end

    tb[n] = id
    tb[n+1] = remain
    tb[n+2] = time_last_update
    tb[n+3] = count
    n = n + 4
end

local order_id = KEYS[2]

for i = 1, #tb, 4 do
    local id = tb[i]
    local remain = tb[i+1]
    local time_last_update = tonumber(tb[i+2])
    local timestamp = tonumber(redis.call('incr', 'timestamp'))
    redis.call('zremrangebyscore', 'food:id:stock', time_last_update, time_last_update)
    redis.call('zadd', 'food:id:stock', timestamp, timestamp * 1000000000 + id * 10000 + remain)
    redis.call('hset', 'food:last_update_time', id, timestamp)
    redis.call('hset', 'order:'..order_id, id, tb[i+3])
end

redis.call('set', 'user:'..user_id..':order', order_id)
redis.call('hset', 'order:user', order_id, user_id)

return 0
