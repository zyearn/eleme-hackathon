-- KEYS[1]: cart_id
-- KEYS[2]: access_token
-- KEYS[3]: time_now
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

local BASETIME = 1447587580

local user_id = redis.call('get', 'token:'..KEYS[2]..':user')
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
    local lef = time_last_update * 10000000 + id * 10000
    local rig = lef + 9999
    local records = redis.call('zrangebyscore', 'food:stock', lef, rig)

    local stock = tonumber(records[1]) % 10000
    local remain = stock - count
    if remain < 0 then
        return -3
    end

    tb[n] = id
    tb[n+1] = remain
    tb[n+2] = lef
    tb[n+3] = rig
    n = n + 4
end

-- local time_redis = redis.call('time')
-- local time_now = (time_redis[1]-BASETIME) * 1000 + math.floor(time_redis[2] / 1000)
local time_now = tonumber(KEYS[3])

for i = 1, #tb, 4 do
    local id = tb[i]
    local remain = tb[i+1]
    local lef = tb[i+2]
    local rig = tb[i+3]
    local score = time_now * 10000000 + id * 10000 + remain
    redis.call('zremrangebyscore', 'food:stock', lef, rig)
    redis.call('zadd', 'food:stock', score, score)
    redis.call('hset', 'food:last_update_time', id, time_now)
end

return 0