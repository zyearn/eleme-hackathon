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


class CartsPostHandler(tornado.web.RequestHandler):
    @check_token
    def post(self, token):
        res = model.cart_create(token)
        self.write({'cart_id': res['cartid']})


class CartsHandler(tornado.web.RequestHandler):
    @check_token
    def patch(self, cartid, token):
        data = parse_request_body(self)
        if not data: return

        foodid = data['food_id']
        count = data['count']
        res = model.cart_add_food(token, cartid, foodid, count)
        if res == 0:
            self.set_status(204)
            self.write('')
        elif res == -1:
            self.set_status(404)
            self.write(const.CART_NOT_FOUND)
        elif res == -2:
            self.set_status(404)
            self.write(const.FOOD_NOT_FOUND)
        elif res == -3:
            self.set_status(403)
            self.write(const.FOOD_OUT_OF_LIMIT)
        else:
            self.set_status(401)
            self.write(const.NOT_AUTHORIZED_TO_ACCESS_CART)

class FoodsHandler(tornado.web.RequestHandler):
    @check_token
    def get(self, token):
        res = model.get_food()
        self.write(json.dumps(res))

class OrdersHandler(tornado.web.RequestHandler):
    @check_token
    def get(self, token):
        res = model.get_order(token)
        if not res:
            self.write(json.dumps([]))
        else:
            ret = []
            ret.append({
                'id': res['orderid'],
                'items': res['items'],
                'total': res['total']
            })
            self.write(json.dumps(ret))

    @check_token
    def post(self, token):
        data = parse_request_body(self)
        if not data: return

        cart_id = data['cart_id']
        ret = model.orders(cart_id, token)
        errcode = ret['err']
        if errcode == 0:
            self.write({"id": ret['order_id']})
        elif errcode == -1:
            self.set_status(404)
            self.write(const.CART_NOT_FOUND)
        elif errcode == -2:
            self.set_status(403)
            self.write(const.NOT_AUTHORIZED_TO_ACCESS_CART)
        elif errcode == -3:
            self.set_status(403)
            self.write(const.FOOD_OUT_OF_STOCK)
        else:
            #errcode == -4
            self.set_status(403)
            self.write(const.ORDER_OUT_OF_LIMIT)

class AdminOrdersHandler(tornado.web.RequestHandler):
    @check_token
    def get(self, token):
        res = model.get_order(token)
        if not res:
            self.write(json.dumps([]))
        else:
            ret = []
            ret.append({
                'id': res['orderid'],
                'items': res['items'],
                'total': res['total'],
                'user_id': res['userid']
            })
            self.write(json.dumps(ret))

if __name__ == "__main__":
    model.sync_redis_from_mysql()
    sys.stderr.write("start serving\n")
    sys.stderr.flush()

    app = tornado.web.Application([
        (r'/login', LoginHandler),
        (r'/carts', CartsPostHandler),
        (r'/carts/(.*)', CartsHandler),
        (r'/foods', FoodsHandler),
        (r'/orders', OrdersHandler),
        (r'/admin/orders', AdminOrdersHandler)
    ], debug=True)

    host = os.getenv("APP_HOST", "localhost")
    port = int(os.getenv("APP_PORT", "8080"))
    app.listen(port=port, address=host)
    tornado.ioloop.IOLoop.current().start()

