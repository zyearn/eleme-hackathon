-- KEYS[1]: cart_id
-- KEYS[2]: order_id
-- KEYS[3]: access_token
-- 
-- return  0: OK
-- return -1: CART_NOT_FOUND
-- return -2: NOT_AUTHORIZED_TO_ACCESS_CART
-- return -3: FOOD_OUT_OF_STOCK
-- return -4: ORDER_OUT_OF_LIMIT

-- 123456689     012     3456
--    time   | food_id | stock
-- 864000000     100     1000   = 10 days <
-- 900719925     474     0992   = 2^53

local user_id = redis.call('get', 'token:'..KEYS[3]..':user')
local belong_user = redis.call('get', 'cart:'..KEYS[1]..':user')
if not belong_user then
    return -1
end

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
    local records = redis.call('zrangebyscore', 'food:stock:count', tonumber(time_last_update), tonumber(time_last_update))

    local stock = tonumber(records[1])
    -- FIXME Stock might be nil!
    assert(stock)
    local remain = stock - count
    if remain < 0 then
            return -3
    end

    tb[n] = id
    tb[n+1] = remain
    tb[n+2] = time_last_update
    n = n + 3
end

for i = 1, #tb, 3 do
    local id = tb[i]
    local remain = tb[i+1]
    local time_last_update = tonumber(tb[i+2])
    local timestamp = tonumber(redis.call('incr', 'timestamp'))
    redis.call('zremrangebyscore', 'food:stock:count', time_last_update, time_last_update)
    redis.call('zremrangebyscore', 'food:stock:kind', time_last_update, time_last_update)
    redis.call('zadd', 'food:stock:count', timestamp, remain)
    redis.call('zadd', 'food:stock:kind' , timestamp, id)
    redis.call('hset', 'food:last_update_time', id, timestamp)
end

local order_id = KEYS[2]

redis.call('set', 'user:'..user_id..':order', order_id)
redis.call('set', 'order:'..order_id..':user', user_id)
redis.call('hset', 'order:cart', order_id, cart_id)


return 0
