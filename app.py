#!/usr/bin/env python3

import os
import sys
import json
import asyncio
import asyncio_redis
from aiohttp import web

import const
import model

@asyncio.coroutine
def parse_request_body(req):
    body = yield from req.read() # maybe use req.json() instead?
    if not body:
        return web.Response(status=400, body=bytes(json.dumps(const.EMPTY_REQUEST), 'utf-8'))

    try:
        data = json.loads(body.decode('utf-8'))
    except (ValueError, KeyError, TypeError) as error:
        return web.Response(status=400, body=bytes(json.dumps(const.MALFORMED_JSON), 'utf-8'))

    return data

def check_token(f):
    def wrapper(req, *arg, **kwargs):
        t1 = req.GET.get('access_token', None)
        t2 = req.headers.get('Access-Token', None)

        if t1 or t2:
            token = t1 if t1 else t2
            if model.is_token_exist(token):
                kwargs['token'] = token
                return f(req, *arg, **kwargs)
        return web.Response(status=401, body=bytes(json.dumps(const.INVALID_ACCESS_TOKEN), 'utf-8'))
    return wrapper

@asyncio.coroutine
def post_login(req):
    data = yield from parse_request_body(req)
    if type(data) is not dict: return data

    username = data['username']
    password = data['password']
    res = yield from model.login(username, password)
    
    if 'err' in res:
        if res['err'] == const.INCORRECT_PASSWORD:
            return web.Response(status=403, body=bytes(json.dumps(const.USER_AUTH_FAIL), 'utf-8'))

    resp = {'user_id':res['userid'], 'username':username, 'access_token':res['token']}
    return web.Response(body=bytes(json.dumps(resp), 'utf-8'))

@asyncio.coroutine
@check_token
def post_carts(req, token):
    res = yield from model.cart_create(token)
    resp = {'cart_id': res['cartid']}
    return web.Response(body=bytes(json.dumps(resp), 'utf-8'))


@asyncio.coroutine
@check_token
def patch_carts(req, token):
    data = yield from parse_request_body(req)
    if type(data) is not dict: return data

    cartid = req.match_info['cartid']

    foodid = data['food_id']
    count = data['count']
    res = yield from model.cart_add_food(token, cartid, foodid, count)
    if res == 0:
        return web.Response(status=204, body=b'')
    elif res == -1:
        return web.Response(status=404, body=bytes(json.dumps(const.CART_NOT_FOUND), 'utf-8'))
    elif res == -2:
        return web.Response(status=404, body=bytes(json.dumps(const.FOOD_NOT_FOUND), 'utf-8'))
    elif res == -3:
        return web.Response(status=403, body=bytes(json.dumps(const.FOOD_OUT_OF_LIMIT), 'utf-8'))
    else:
        return web.Response(status=401, body=bytes(json.dumps(const.NOT_AUTHORIZED_TO_ACCESS_CART), 'utf-8'))

@asyncio.coroutine
@check_token
def get_foods(req, token):
    res = yield from model.get_food()
    return web.Response(body=bytes(json.dumps(res), 'utf-8'))

@asyncio.coroutine
@check_token
def get_orders(req, token):
    res = yield from model.get_order(token)
    if not res:
        return web.Response(body=bytes(json.dumps([]), 'utf-8'))
    else:
        ret = []
        ret.append({
            'id': res['orderid'],
            'items': res['items'],
            'total': res['total']
        })
        return web.Response(body=bytes(json.dumps(ret), 'utf-8'))

@asyncio.coroutine
@check_token
def post_orders(req, token):
    data = yield from parse_request_body(req)
    if type(data) is not dict: return data

    cart_id = data['cart_id']
    ret = yield from model.place_order(cart_id, token)
    errcode = ret['err']
    if errcode == 0:
        resp = {"id": ret['order_id']}
        return web.Response(body=bytes(json.dumps(resp), 'utf-8'))
    elif errcode == -1:
        return web.Response(status=404, body=bytes(json.dumps(const.CART_NOT_FOUND), 'utf-8'))
    elif errcode == -2:
        return web.Response(status=403, body=bytes(json.dumps(const.NOT_AUTHORIZED_TO_ACCESS_CART), 'utf-8'))
    elif errcode == -3:
        return web.Response(status=403, body=bytes(json.dumps(const.FOOD_OUT_OF_STOCK), 'utf-8'))
    else:
        #errcode == -4
        return web.Response(status=403, body=bytes(json.dumps(const.ORDER_OUT_OF_LIMIT), 'utf-8'))

@asyncio.coroutine
@check_token
def get_admin_orders(req, token):
    res = yield from model.get_order(token)
    if not res:
        return web.Response(body=bytes(json.dumps([]), 'utf-8'))
    else:
        ret = []
        ret.append({
            'id': res['orderid'],
            'items': res['items'],
            'total': res['total'],
            'user_id': res['userid']
        })
        return web.Response(body=bytes(json.dumps(ret), 'utf-8'))

if __name__ == "__main__":
    host = os.getenv("APP_HOST", "localhost")
    port = int(os.getenv("APP_PORT", "8080"))

    app = web.Application()
    app.router.add_route('POST',  '/login',          post_login)
    app.router.add_route('POST',  '/carts',          post_carts)
    app.router.add_route('PATCH', '/carts/{cartid}', patch_carts)
    app.router.add_route('GET',   '/foods',          get_foods)
    app.router.add_route('GET',   '/orders',         get_orders)
    app.router.add_route('POST',  '/orders',         post_orders)
    app.router.add_route('GET',   '/admin/orders',   get_admin_orders)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(model.init())
    handler = app.make_handler()
    f = loop.create_server(handler, host, port)
    srv = loop.run_until_complete(f)
    print('serving on', srv.sockets[0].getsockname())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(handler.finish_connections(1.0))
        srv.close()
        loop.run_until_complete(model.close())
        loop.run_until_complete(srv.wait_closed())
        loop.run_until_complete(app.finish())
    loop.close()
