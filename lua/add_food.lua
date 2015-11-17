-- KEYS[1]: access_token
-- KEYS[2]: cart_id
-- KEYS[3]: food_id
-- KEYS[4]: count
-- 
-- return  0: OK
-- return -1: CART_NOT_FOUND
-- return -3: FOOD_OUT_OF_LIMIT
-- return -4: NOT_AUTHORIZED_TO_ACCESS_CART

local belong_user = redis.call('get', 'token:'..KEYS[1]..':user'); 
local cart_user = redis.call('get', 'cart:'..KEYS[2]..':user');
if not cart_user then
    return -1
end
if cart_user == belong_user then
    local origin = redis.call('hgetall', 'cart:'..KEYS[2]);
    local sum = 0;
    for i = 2,#origin, 2 do
        sum = sum + origin[i]
    end
    if sum + KEYS[4] > 3 then
        return -3;
    end
    redis.call('hincrby', 'cart:'..KEYS[2], KEYS[3], KEYS[4])
    return 0
else
    return -4
end
