#!/usr/bin/env python3

import os
import time
import json
import redis
import falcon

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

def init():
    global r, func
    r = redis.StrictRedis(host=HOST, port=PORT, db=0, decode_responses=True)
    func = r.register_script(gen_script('falcon'))

def run_redis_py():
    st = time.time()
    func(keys=[])
    ed = time.time()
    return ed-st

class IndexHandler:
    def on_get(self, req, resp):
        dt = run_redis_py()
        resp.body = json.dumps({'time': dt})

init()
api = falcon.API()
api.add_route('/', IndexHandler())

# Time per request:       33.425 [ms] (mean)
# Time per request:       0.669 [ms] (mean, across all concurrent requests)