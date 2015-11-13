import os
import redis
import sys
import pymysql
import pymysql.cursors

r = redis.StrictRedis(host=os.getenv("REDIS_HOST", "localhost"), 
                    port=os.getenv("REDIS_PORT", 6379), 
                    db=0)

mysqlconn = pymysql.connect(host=os.getenv("DB_HOST", "localhost"),
                           port=int(os.getenv("DB_PORT", 3306)),
                           user=os.getenv("DB_USER", "root"),
                           passwd=os.getenv("DB_PASS", "toor"),
                           db=os.getenv("DB_NAME", "eleme"),
                           cursorclass=pymysql.cursors.DictCursor,
                           autocommit=True)

with mysqlconn.cursor() as cursor:
    sql = "select id,name,password from user"
    cursor.execute(sql)
    results = cursor.fetchall()
    for result in results:
        r.set('username:'+result['name']+':password', result['password'])
        r.set('username:'+result['name']+':userid', result['id'])

    cursor.execute("select id,stock,price from food")
    results = cursor.fetchall()
    r.delete('food_list')
    for result in results:
        r.set('food:'+str(result['id'])+':stock', result['stock'])
        r.set('food:'+str(result['id'])+':price', result['price'])
        r.rpush('food_list', result['id'])

sys.stderr.write('transfer data from mysql to redis done\n')
sys.stderr.flush()
