import os
import sys
import redis
import random
import string
import pymysql
import pymysql.cursors
import time
import math
import asyncio
import asyncio_redis

import const

TOKEN_LENGTH = 8

r = None
lua_add_food = None
lua_place_order = None
lua_query_stock = None
lua_time = None

cache_food_last_update_time = 0
cache_food_price = {}
cache_food_stock = {}
cache_token_user = {}
cache_userid = {}
cache_user = {}

@asyncio.coroutine
def register_lua_script(name):
    with open('lua/%s.lua'%name) as f:
        script = f.read()
        func = r.register_script(script)
    return func

@asyncio.coroutine
def call_lua_script(script, keys):
    for i in range(len(keys)):
        keys[i] = '{}'.format(keys[i])
    reply = yield from script.run(keys=keys)
    result = yield from reply.return_value()
    return result

def sync_redis_from_mysql():
    # still use redis-py here
    r = redis.StrictRedis(host=os.getenv("REDIS_HOST", "localhost"), 
                          port=os.getenv("REDIS_PORT", 6379), 
                          db=0, decode_responses=True)
    if const.DEBUG:
        sys.stderr.write('WARNING! DEBUG MODE! Remember to set `const.DEBUG = False` in production!\n')
        sys.stderr.write('                     Redis FLUSHALL\n')
        sys.stderr.flush()
        r.flushall()
        r.script_flush()

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

    now = 0

    with mysqlconn.cursor() as cursor:
        p = r.pipeline()
        sec, milli = map(float, r.time())
    global lua_add_food, lua_place_order, lua_query_stock
    lua_add_food = register_lua_script('add_food')
    lua_place_order = register_lua_script('place_order')
    lua_query_stock = register_lua_script('query_stock')

    with mysqlconn.cursor() as cursor:
        p = r.pipeline()
        global cache_food_last_update_time
        cache_food_last_update_time = 0

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
            now += 1
            cache_food_price[id] = price
            cache_food_stock[id] = stock
            p.zadd(const.FOOD_STOCK_KIND, now, now*const.TIME_BASE + id)
            p.zadd(const.FOOD_STOCK_COUNT, now, now* const.TIME_BASE + stock)
            p.hset(const.FOOD_LAST_UPDATE_TIME, id, now)
        p.set(const.TIMESTAMP, now)
        p.execute()

@asyncio.coroutine
def init():
    global r, lua_add_food, lua_place_order, lua_query_stock, lua_time

    sync_redis_from_mysql()
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    r = yield from asyncio_redis.Connection.create(host, port)
    lua_add_food = yield from register_lua_script('add_food')
    lua_place_order = yield from register_lua_script('place_order')
    lua_query_stock = yield from register_lua_script('query_stock')
    lua_time = yield from register_lua_script('time')

# generate random string
def random_string(length=TOKEN_LENGTH):
    return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(length)])

# login
@asyncio.coroutine
def login(username, password):
    userid = cache_userid.get(username, None)
    pwd = cache_user[userid]['password'] if userid != None else None
    if userid == None or password != pwd:
        return { 'err': const.INCORRECT_PASSWORD }

    token = random_string(TOKEN_LENGTH)
    yield from r.set('token:%s:user'%token, '{}'.format(userid))
    cache_token_user[token] = userid
    return { 'userid': userid, 'token': token }

@asyncio.coroutine
def get_token_user(token):
    if token in cache_token_user:
        return cache_token_user[token]
    uid = yield from r.get('token:%s:user'%token)
    if uid:
        cache_token_user[token] = uid
    return uid

# check access_token
@asyncio.coroutine
def is_token_exist(token):
    return (yield from get_token_user(token))

# create cart
@asyncio.coroutine
def cart_create(token):
    userid = yield from get_token_user(token)
    cartid = random_string(TOKEN_LENGTH)
    yield from r.set('cart:%s:user'%cartid, '{}'.format(userid))
    return { 'cartid': cartid }

@asyncio.coroutine
def cart_add_food(token, cart_id, food_id, count):
    if is_food_exist(food_id):
        res = yield from call_lua_script(lua_add_food, [token, cart_id, food_id, count])
    else:
        res = -2
    return res

def is_food_exist(food_id):
    return int(food_id) in cache_food_price

@asyncio.coroutine
def get_food():
    global cache_food_last_update_time
    stock_delta = yield from call_lua_script(lua_query_stock, [cache_food_last_update_time])
    cache_food_last_update_time = stock_delta[1]
    for i in range(2, len(stock_delta), 2):
        id = int(stock_delta[i])
        stock = int(stock_delta[i+1])
        cache_food_stock[id] = stock
    return [{
        'id': k,
        'price': cache_food_price[k],
        'stock': cache_food_stock[k]
    } for k in cache_food_price]

@asyncio.coroutine
def place_order(cart_id, token):
    order_id = random_string()
    rtn = yield from call_lua_script(lua_place_order, [cart_id, order_id, token])
    result = {'err': rtn}
    if rtn == 0:
        result['order_id'] = order_id

    return result

@asyncio.coroutine
def get_order(token):
    userid = yield from get_token_user(token)
    orderid = yield from r.get('user:%s:order'%userid)
    if not orderid:
        return None
    cartid = yield from r.hget('order:cart', orderid)
    items = yield from r.hgetall('cart:%s'%cartid)
    item_arr = []
    prices = {}
    total = 0
    for handle in items:
        food, count = yield from handle
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

@asyncio.coroutine
def close():
    r.close()
    yield
