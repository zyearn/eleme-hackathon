#!/usr/bin/env python3

import os
import sys
import tornado.ioloop
import tornado.web
import json

import const
import model

def parse_request_body(self):
    if not self.request.body:
        self.set_status(400)
        self.write(const.EMPTY_REQUEST)
        return False

    try:
        data = json.loads(self.request.body.decode('utf-8'))
    except (ValueError, KeyError, TypeError) as error:
        self.set_status(400)
        self.write(const.MALFORMED_JSON)
        return False

    return data

def check_token(f):
    def wrapper(self, *arg, **kwargs):
        t1 = self.get_argument('access_token', None)
        t2 = self.request.headers.get('Access-Token', None)

        if t1 or t2:
            token = t1 if t1 else t2
            if model.is_token_exist(token):
                kwargs['token'] = token
                f(self, *arg, **kwargs)
                return
        self.set_status(401)
        self.write(const.INVALID_ACCESS_TOKEN)
    return wrapper


class LoginHandler(tornado.web.RequestHandler):
    def post(self):
        data = parse_request_body(self)
        if not data: return

        username = data['username']
        password = data['password']
        res = model.login(username, password)
        
        if 'err' in res:
            if res['err'] == const.INCORRECT_PASSWORD:
                self.set_status(403)
                self.write(const.USER_AUTH_FAIL)
            return
        self.write({'user_id':res['userid'], 'username':username, 'access_token':res['token']})



class CartsHandler(tornado.web.RequestHandler):

    @check_token
    def post(self, token):
        res = model.cart_create(token)
        self.write({'cart_id': res['cartid']})

if __name__ == "__main__":
    model.sync_redis_from_mysql() # FIX ME!!!

    app = tornado.web.Application([
        (r'/login', LoginHandler),
        (r'/carts', CartsHandler)
    ], debug=True)

    host = os.getenv("APP_HOST", "localhost")
    port = int(os.getenv("APP_PORT", "8080"))
    app.listen(port=port, address=host)
    tornado.ioloop.IOLoop.current().start()
