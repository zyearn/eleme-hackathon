DEBUG = True


INCORRECT_PASSWORD = '## INCORRECT_PASSWORD'

USER_AUTH_FAIL = {'code':'USER_AUTH_FAIL', 'message':'用户名或密码错误'}
INVALID_ACCESS_TOKEN = {"code": "INVALID_ACCESS_TOKEN", "message": "无效的令牌"}
EMPTY_REQUEST = {'code':'EMPTY_REQUEST', 'message':'请求体为空'}
MALFORMED_JSON = {'code':'MALFORMED_JSON', 'message':'格式错误'}

### transfer redis to mysql initialization key
INIT_TIME = 'INIT_TIME'
REDIS_BASETIME = 1447587580

### error code for orders
CART_NOT_FOUND = {'code':'CART_NOT_FOUND', 'message':'篮子不存在'}
NOT_AUTHORIZED_TO_ACCESS_CART = {'code':'NOT_AUTHORIZED_TO_ACCESS_CART', 'message':'无权限访问指定的篮子'}
FOOD_OUT_OF_STOCK = {'code':'FOOD_OUT_OF_STOCK', 'message':'食物库存不足'}
ORDER_OUT_OF_LIMIT = {'code':'ORDER_OUT_OF_LIMIT', 'message':'每个用户只能下一单'}
FOOD_NOT_FOUND = {"code": "FOOD_NOT_FOUND", "message": "食物不存在"}
FOOD_OUT_OF_LIMIT = {"code": "FOOD_OUT_OF_LIMIT", "message": "篮子中食物数量超过了三个"}

### const key name
FOOD_STOCK = 'food:stock'
FOOD_LAST_UPDATE_TIME = 'food:last_update_time'

