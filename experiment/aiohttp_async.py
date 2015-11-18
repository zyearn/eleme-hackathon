#!/usr/bin/env python3.4

import os
import json
import time
import redis
import asyncio
import asyncio_redis
from aiohttp import web

HOST = os.getenv("REDIS_HOST", "localhost")
PORT = int(os.getenv("REDIS_PORT", 6379))

r = None
func = None

def gen_script(prefix):
    return """
local tot = 10
for i = 1, tot, 1 do
    redis.call('set', '{0}:' .. tostring(i), i)
end
local sum = 0
for i = 1, tot, 1 do
    local str = redis.call('get', '{0}:' .. tostring(i))
    sum = sum + tostring(str)
end
return sum
    """.format(prefix)

@asyncio.coroutine
def init():
    global r, func
    r = yield from asyncio_redis.Connection.create(HOST, PORT)
    func = yield from r.register_script(gen_script('asyncio-redis'))

@asyncio.coroutine
def close():
    r.close()
    yield


@asyncio.coroutine
def query():
    st = time.time()
    reply = yield from func.run(keys=[])
    #yield from reply.return_value()
    ed = time.time()
    return ed-st


@asyncio.coroutine
def get_handler(request):
    dt = yield from query()
    return web.Response(body=bytes(json.dumps({'time': dt}), 'utf-8'))

if __name__ == "__main__":
    init()

    app = web.Application()
    app.router.add_route('GET', '/', get_handler)

    host = os.getenv("APP_HOST", "localhost")
    port = int(os.getenv("APP_PORT", "8080"))
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init())
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
        loop.run_until_complete(close())
        srv.close()
        loop.run_until_complete(srv.wait_closed())
        loop.run_until_complete(app.finish())
    loop.close()

# Time per request:       43.955 [ms] (mean)
# Time per request:       0.879 [ms] (mean, across all concurrent requests)