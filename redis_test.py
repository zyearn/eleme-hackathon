#!/usr/bin/env python3

import os
import time
import redis
import tornado.ioloop
import tornado.web

HOST = os.getenv("REDIS_HOST", "localhost")
PORT = int(os.getenv("REDIS_PORT", 6379))

r = None
func = None

def gen_script(prefix):
    return """
local tot = 100
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

def init():
    global r, func
    r = redis.StrictRedis(host=HOST, port=PORT, db=0, decode_responses=True)
    func = r.register_script(gen_script('redis-py'))

def run_redis_py():
    st = time.time()
    func(keys=[])
    ed = time.time()
    return ed-st

class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        dt = run_redis_py()
        self.write({'time': dt})

if __name__ == "__main__":
    init()

    app = tornado.web.Application([
        (r'/', IndexHandler)
    ])

    host = os.getenv("APP_HOST", "localhost")
    port = int(os.getenv("APP_PORT", "8080"))
    app.listen(port=port, address=host)
    tornado.ioloop.IOLoop.current().start()