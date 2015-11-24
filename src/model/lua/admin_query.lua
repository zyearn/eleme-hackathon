local ret = {}

local n  = 1
local records_order_user = redis.call('hgetall', 'order:user')
for i = 1, #records_order_user, 2 do
    ret[n] = {}
    ret[n][1] = records_order_user[i]
    ret[n][2] = records_order_user[i+1]
    ret[n][3] = redis.call('hgetall', 'order:'..records_order_user[i])
    n = n+1
end

return ret
