import os
import redis
import sys
import random
import string
import pymysql
import pymysql.cursors
import const
import orderslua

r = redis.StrictRedis(host=os.getenv("REDIS_HOST", "localhost"), 
                      port=os.getenv("REDIS_PORT", 6379), 
                      db=0, decode_responses=True)

orders_lua = r.register_script(orderslua.orders)
TOKEN_LENGTH = 8

# sync redis from mysql
def sync_redis_from_mysql():
    if r.incr(const.INIT_TIME) == 1:
        sys.stderr.write("ready to init redis\n")
        sys.stderr.flush()
    else:
        sys.stderr.write("redis has already been init\n")
        sys.stderr.flush()
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
            p.set('username:%s:password'%result['name'], result['password'])
            p.set('username:%s:userid'%result['name'], result['id'])

        cursor.execute("select id,stock,price from food")
        results = cursor.fetchall()
        p.delete(const.FOOD_SET)
        for result in results:
            p.hset(const.FOOD_STOCK, result['id'], result['stock'])
            p.hset(const.FOOD_PRICE, result['id'], result['price'])
            p.sadd(const.FOOD_SET, result['id'])

        p.execute()

# generate random string
def random_string(length=TOKEN_LENGTH):
    return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(length)])

# login
def login(username, password):
    userid = r.get('username:%s:userid' % username)
    pwd = r.get('username:%s:password' % username)
    if not userid or password != pwd:
        return { 'err': const.INCORRECT_PASSWORD }

    token = random_string(TOKEN_LENGTH)
    r.set('token:%s:user'%token, userid)
    return { 'userid': userid, 'token': token }

# check access_token
def is_token_exist(token):
    return r.exists('token:%s:user'%token)

# query stocks of all foods
def query_stocks():
    pass

# create cart
def cart_create(token):
    userid = r.get('token:%s:user'%token)
    cartid = random_string(TOKEN_LENGTH)
    r.set('cart:%s:user'%cartid, userid)
    return { 'cartid': cartid }

def is_food_exist(food_id):
    return r.sismember(const.FOOD_SET, food_id)

def get_food():
    food_price = r.hgetall(const.FOOD_PRICE)
    food_stock = r.hgetall(const.FOOD_STOCK)
    result = []
    for (k,v), (k2,v2) in zip(food_price.items(), food_stock.items()):
        result.append({'id':int(k), 'price':int(v), 'stock':int(v2)})
    return result


def orders(cart_id, token):
    rtn = orders_lua(keys=[cart_id, token])
    result = {'err': rtn}
    if rtn == 0:
        user_id = r.get('token:%s:user' % token)
        order_id = random_string()
        r.set('user:%s:order' % str(user_id), order_id)
        r.set('order:%s:user' % order_id, user_id)
        r.hset('order:cart', order_id, cart_id)
        result['order_id'] = order_id

    return result

