import os
import redis
import sys
import pymysql
import pymysql.cursors

r = redis.StrictRedis(host=os.getenv("REDIS_HOST", "localhost"), 
                      port=os.getenv("REDIS_PORT", 6379), 
                       db=0)

TOKEN_LENGTH = 8

# sync redis from mysql
def sync_redis_from_mysql():
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
        p.delete('food_list')
        for result in results:
            p.set('food:%d:stock'%result['id'], result['stock'])
            p.set('food:%d:price'%result['id'], result['price'])
            p.rpush('food_list', result['id'])

        p.execute()

# generate random string
def random_string(length):
    return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(length)])

# login
def login(username, password):
    userid = r.get('username:%s:userid' % username)
    pwd = r.get('username:%s:password' % username)
    if password != pwd:
        return False
    token = random_string(TOKEN_LENGTH)
    r.set('token:%s:user'%token, userid)
    return token

# access_token check decorator
def check_access_token(f):
    def wrapper(token, *args, **kwargs):
        userid = r.get('token:%s:user'%token)
        if not userid:
            return False
        f((token, userid), *args, **kwargs)
    return wrapper

# query stocks of all foods
def query_stocks():
    pass

# create cart
@check_access_token
def create_cart(access_token):
    token, userid = access_token
    cartid = random_string(TOKEN_LENGTH)
    r.set('cart:%s:user'%cartid, userid)
    return cartid
