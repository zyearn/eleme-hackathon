#!/usr/bin/env python3

import os
import tornado.ioloop
import tornado.web
import pymysql
import pymysql.cursors
import json
import redis
import transfer

def conn():
    return pymysql.connect(host=os.getenv("DB_HOST", "localhost"),
                           port=int(os.getenv("DB_PORT", 3306)),
                           user=os.getenv("DB_USER", "root"),
                           passwd=os.getenv("DB_PASS", "toor"),
                           db=os.getenv("DB_NAME", "eleme"),
                           cursorclass=pymysql.cursors.DictCursor,
                           autocommit=True)
mysqlconn = None

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

        with mysqlconn.cursor() as cursor:
            sql = "select id, name from user where name=%s and password=%s"
            cursor.execute(sql, (data['username'], data['password']))
            result = cursor.fetchone()

        if result:
            self.write({'user_id':result['id'], 'username':result['name'], 'access_token':'xxdabc'})
        else:
            self.set_status(403)
            self.write({'code':'USER_AUTH_FAIL', 'message':'用户名或密码错误'})

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
