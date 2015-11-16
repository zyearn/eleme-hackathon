import os
import redis
import sys
import random
import string
import pymysql
import pymysql.cursors
import time
import math

import const

TOKEN_LENGTH = 8

r = redis.StrictRedis(host=os.getenv("REDIS_HOST", "localhost"), 
                      port=os.getenv("REDIS_PORT", 6379), 
                      db=0, decode_responses=True)

cache_food_last_update_time = 0
cache_food_price = {}
cache_food_stock = {}
cache_token_user = {}
cache_userid = {}
cache_user = {}

def register_lua_script(name):
    with open('lua/%s.lua'%name) as f:
        script = f.read()
        func = r.register_script(script)
    return func


# sync redis from mysql
def sync_redis_from_mysql():
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
<<<<<<< HEAD

    with mysqlconn.cursor() as cursor:
        p = r.pipeline()
        sec, milli = map(float, r.time())
=======
    global lua_add_food, lua_place_order, lua_query_stock
    lua_add_food = register_lua_script('add_food')
    lua_place_order = register_lua_script('place_order')
    lua_query_stock = register_lua_script('query_stock')

    with mysqlconn.cursor() as cursor:
        p = r.pipeline()
>>>>>>> [Buggy] Change the implementation of food:stock
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
            p.zadd(const.FOOD_STOCK_KIND, now, id)
<<<<<<< HEAD
            p.zadd(const.FOOD_STOCK_COUNT, now, stock)
            p.hset(const.FOOD_LAST_UPDATE_TIME, id, now)
=======
            p.zadd(const.FOOD_STOCK_COUNT, now, int(stock))
            p.hset(const.FOOD_LAST_UPDATE_TIME, id, int(now))
>>>>>>> [Buggy] Change the implementation of food:stock
        p.set(const.TIMESTAMP, now)
        p.execute()

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
    cache_token_user[token] = userid
    return { 'userid': userid, 'token': token }

def get_token_user(token):
    if token in cache_token_user:
        return cache_token_user[token]
    uid = r.get('token:%s:user'%token)
    if uid:
        cache_token_user[token] = uid
    return uid

# check access_token
def is_token_exist(token):
    return get_token_user(token)

# create cart
def cart_create(token):
    userid = get_token_user(token)
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
    global cache_food_last_update_time
    stock_delta = lua_query_stock(keys=[cache_food_last_update_time])
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

def place_order(cart_id, token):
    order_id = random_string()
    rtn = lua_place_order(keys=[cart_id, order_id, token])
    result = {'err': rtn}
<<<<<<< HEAD
    sys.stderr.write(rtn)
=======
    if rtn: sys.stderr.write(rtn)
>>>>>>> [Buggy] Change the implementation of food:stock
    if rtn == 0:
        result['order_id'] = order_id

    return result

def get_order(token):
    userid = get_token_user(token)
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

