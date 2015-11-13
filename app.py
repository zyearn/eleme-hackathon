#!/usr/bin/env python3

import os
import sys
import tornado.ioloop
import tornado.web
import pymysql
import pymysql.cursors
import json
import redis
import transfer
import string
import random

def id_generator(size=8, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

def conn():
    return pymysql.connect(host=os.getenv("DB_HOST", "localhost"),
                           port=int(os.getenv("DB_PORT", 3306)),
                           user=os.getenv("DB_USER", "root"),
                           passwd=os.getenv("DB_PASS", "toor"),
                           db=os.getenv("DB_NAME", "eleme"),
                           cursorclass=pymysql.cursors.DictCursor,
                           autocommit=True)
mysqlconn = None
pool = redis.ConnectionPool(host=os.getenv("REDIS_HOST", "localhost"),
                        port=os.getenv("REDIS_PORT", 6379), 
                        db=0)

class HelloHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world")

class LoginHandler(tornado.web.RequestHandler):
    def post(self):
        if not self.request.body:
            self.set_status(400)
            self.write({'code':'EMPTY_REQUEST', 'message':'请求体为空'})
            return

        try:
            data = json.loads(self.request.body.decode('utf-8'))
        except (ValueError, KeyError, TypeError) as error:
            self.set_status(400)
            self.write({'code':'MALFORMED_JSON', 'message':'格式错误'})
            return

        r = redis.Redis(connection_pool=pool)
        password = r.get('username:'+data['username']+':password')
        if password is None or password.decode('utf-8') != data['password']:
            self.set_status(403)
            self.write({'code':'USER_AUTH_FAIL', 'message':'用户名或密码错误'})
            return
        
        userId = r.get('username:'+data['username']+':userid').decode('utf-8');
        actoken = id_generator();
        r.set('token:'+actoken+':user', userId);
        self.write({'user_id':userId, 'username':data['username'], 'access_token':actoken})

if __name__ == "__main__":
    app = tornado.web.Application([
        (r"/", HelloHandler),
        (r'/login', LoginHandler)
    ], debug=True)

    host = os.getenv("APP_HOST", "localhost")
    port = int(os.getenv("APP_PORT", "8080"))
    app.listen(port=port, address=host)
    mysqlconn = conn()
    tornado.ioloop.IOLoop.current().start()
