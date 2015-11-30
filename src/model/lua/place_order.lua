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

local tb = {n=9}
local n = 1
local cart_items = redis.call('hgetall', 'cart:'..KEYS[1])
for i = 1, #cart_items, 2 do
    local id = tonumber(cart_items[i])
    local count = tonumber(cart_items[i+1])

    local stock = redis.call('hget', 'food:stock', id)
    local remain = stock - count
    if remain < 0 then
            return -3
    end

    tb[n] = id
    tb[n+1] = remain
    tb[n+2] = count
    n = n + 3
end

local order_id = KEYS[2]

for i = 1, #tb, 3 do
    redis.call('hset', 'food:stock', tb[i], tb[i+1])
    redis.call('hset', 'order:'..order_id, tb[i], tb[i+2])
end

redis.call('set', 'user:'..user_id..':order', order_id)
redis.call('hset', 'order:user', order_id, user_id)

return 0
