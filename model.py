import os
import redis
import sys
import random
import string
import pymysql
import pymysql.cursors
import const
import time

TOKEN_LENGTH = 8

r = redis.StrictRedis(host=os.getenv("REDIS_HOST", "localhost"), 
                      port=os.getenv("REDIS_PORT", 6379), 
                      db=0, decode_responses=True)

cache_food_price = {}
cache_userid = {}
cache_user = {}

def register_lua_script(name):
    with open('lua/%s.lua'%name) as f:
        script = f.read()
        func = r.register_script(script)
    return func

lua_add_food = register_lua_script('add_food')
lua_orders = register_lua_script('orders')

# sync redis from mysql
def sync_redis_from_mysql():
    if const.DEBUG:
        sys.stderr.write('WARNING! DEBUG MODE! Remember to set `const.DEBUG = False` in production!\n')
        sys.stderr.write('                     Redis FLUSHALL\n')
        sys.stderr.flush()
        r.flushall()

    if r.incr(const.INIT_TIME) == 1:
        sys.stderr.write("ready to init redis\n")
        sys.stderr.flush()
    else:
        sys.stderr.write("redis has already been init\n")
        sys.stderr.flush()
        while int(r.get(const.INIT_TIME)) >= 1:
            time.sleep(0.1)
        return

    mysqlconn = pymysql.connect(host=os.getenv("DB_HOST", "localhost"),
                               port=int(os.getenv("DB_PORT", 3306)),
                               user=os.getenv("DB_USER", "root"),
                               passwd=os.getenv("DB_PASS", "toor"),
                               db=os.getenv("DB_NAME", "eleme"),
                               cursorclass=pymysql.cursors.DictCursor,
                               autocommit=True)

    with mysqlconn.cursor() as cursor:
        p = r.pipeline()

        cursor.execute("select id,name,password from user")
        results = cursor.fetchall()
        for result in results:
            id, name, pwd = result['id'], result['name'], result['password']
            cache_user[id] = { 'id': id, 'name': name, 'password': pwd }
            cache_userid[name] = id

        cursor.execute("select id,stock,price from food")
        results = cursor.fetchall()
        for result in results:
            id, stock, price = result['id'], result['stock'], result['price']

            cache_food_price[id] = price
            p.hset(const.FOOD_STOCK, id, stock)

        p.execute()
    r.set(const.INIT_TIME, -10000)

# generate random string
def random_string(length=TOKEN_LENGTH):
    return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(length)])

# login
def login(username, password):
    userid = cache_userid.get(username, None)
    pwd = cache_user[userid]['password'] if userid != None else None
    if userid == None or password != pwd:
        return { 'err': const.INCORRECT_PASSWORD }

    token = random_string(TOKEN_LENGTH)
    r.set('token:%s:user'%token, userid)
    return { 'userid': userid, 'token': token }

# check access_token
def is_token_exist(token):
    return r.exists('token:%s:user'%token)

# create cart
def cart_create(token):
    userid = r.get('token:%s:user'%token)
    cartid = random_string(TOKEN_LENGTH)
    r.set('cart:%s:user'%cartid, userid)
    return { 'cartid': cartid }

def cart_add_food(token, cart_id, food_id, count):
    if is_food_exist(food_id):
        res = lua_add_food(keys=[token, cart_id, food_id, count])
    else:
        res = -2
    return res

def is_food_exist(food_id):
    return int(food_id) in cache_food_price

def get_food():
    food_stock = r.hgetall(const.FOOD_STOCK)
    return [{
        'id':int(k), 
        'price':int(cache_food_price[k]), 
        'stock':int(food_stock['%d'%k])
    } for k in cache_food_price]

def orders(cart_id, token):
    rtn = lua_orders(keys=[cart_id, token])
    result = {'err': rtn}
    if rtn == 0:
        user_id = r.get('token:%s:user' % token)
        order_id = random_string()
        r.set('user:%s:order' % str(user_id), order_id)
        r.set('order:%s:user' % order_id, user_id)
        r.hset('order:cart', order_id, cart_id)
        result['order_id'] = order_id

    return result

def get_order(token):
    userid = r.get('token:%s:user'%token)
    orderid = r.get('user:%s:order'%userid)
    if not orderid:
        return None
    cartid = r.hget('order:cart', orderid)
    items = r.hgetall('cart:%s'%cartid)
    item_arr = []
    prices = {}
    total = 0
    for food, count in items.items():
        f, c = int(food), int(count)
        price = cache_food_price[f]
        total += price * c
        item_arr.append({'food_id': f, 'count': c})
    return {
        'userid': int(userid),
        'orderid': orderid,
        'items': item_arr,
        'total': total
    }

