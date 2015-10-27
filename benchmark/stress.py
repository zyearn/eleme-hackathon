from __future__ import print_function

import argparse
import contextlib
import json
import random
import time
import pymysql
import os
import redis
import functools
import math
import traceback
import itertools
import signal

try:
    import httplib
except ImportError:
    import http.client as httplib

try:
    import urllib.parse as urllib
except ImportError:
    import urllib

from multiprocessing.pool import Pool, ThreadPool
from multiprocessing import Process

KEY_PREFIX = "stress_test:make_order"
FAILURE_KEY = "{}:failure".format(KEY_PREFIX)
SUCCESS_KEY = "{}:success".format(KEY_PREFIX)
RESPONSE_TIME_KEY = "{}:response_time".format(KEY_PREFIX)
REQUEST_TIME_KEY = "{}:request_time".format(KEY_PREFIX)
REQUEST_KEY = "{}:request".format(KEY_PREFIX)
REQUEST_FAILD_KEY = "{}:request:failed".format(KEY_PREFIX)
USER_KEY = "{}:user".format(KEY_PREFIX)
ORDER_EVERY_SEC_KEY = "{}:orders_every_sec".format(KEY_PREFIX)

redis_store = redis.Redis()
users = foods = None


@contextlib.contextmanager
def db_query():
    db = pymysql.connect(host=os.getenv("DB_HOST", "localhost"),
                         port=int(os.getenv("DB_PORT", 3306)),
                         user=os.getenv("DB_USER", "root"),
                         passwd=os.getenv("DB_PASS", "toor"),
                         db=os.getenv("DB_NAME", "eleme"))
    try:
        yield db
    finally:
        db.close()


def load_users():
    users = {}
    with db_query() as db:
        cur = db.cursor()

        # load users
        cur.execute("SELECT id, name, password FROM user")

        for i, name, pw in cur.fetchall():
            users[i] = {"username": name, "password": pw}
    redis_store.sadd(USER_KEY, *users.keys())
    return users


def load_foods():
    foods = []
    with db_query() as db:
        cur = db.cursor()
        cur.execute("SELECT id, stock, price FROM food")

        for i, stock, price in cur.fetchall():
            foods.append({"id": i, "stock": stock})
    return foods


def safe_loads(data):
    try:
        return json.loads(data)
    except Exception:
        return data


class QueryException(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return "{} {}".format(self.code, self.message)


class Query(object):
    def __init__(self, host, port):
        self.access_token = None
        self.user_id = None
        self.cart_id = None

        self.client = httplib.HTTPConnection(host, port, timeout=3)

    def request(self, method, url, headers=None, data=None):
        data = data or {}
        headers = headers or {}
        headers["Content-Type"] = "application/json"

        start = time.time()
        self.client.request(method, url, body=json.dumps(data),
                            headers=headers)
        response = self.client.getresponse()
        status = response.status
        data = response.read().decode("ascii")
        self.client.close()
        elapsed = time.time() - start

        if status in (200, 204):
            redis_store.incr(REQUEST_KEY)
            redis_store.lpush(REQUEST_TIME_KEY, elapsed)
        else:
            redis_store.incr(REQUEST_FAILD_KEY)
        return {"status": status, "data": safe_loads(data)}

    def url(self, path):
        assert self.access_token
        params = {"access_token": self.access_token}
        qs = urllib.urlencode(params)
        return "{}?{}".format(path, qs) if qs else path

    def _do_login(self, username, password):
        data = {
            "username": username,
            "password": password
        }
        response = self.request("POST", "/login", data=data)
        if response["status"] == 200:
            self.access_token = response["data"]["access_token"]
            return True
        return False

    def login(self):
        user_id = redis_store.spop(USER_KEY)
        self.user_id = int(user_id)
        user = users[self.user_id]
        return self._do_login(user["username"], user["password"])

    def get_foods(self):
        res = self.request("GET", self.url("/foods"))
        return res["status"] == 200

    def get_orders(self):
        res = self.request("GET", self.url("/orders"))
        return res["status"] == 200

    def create_cart(self):
        response = self.request("POST", self.url("/carts"))
        try:
            self.cart_id = response["data"].get("cart_id")
        except Exception:
            return False
        return response["status"] == 200

    def cart_add_food(self):
        food = random.choice(foods)
        data = {"food_id": food["id"], "count": 1}
        path = "/carts/{}".format(self.cart_id)
        res = self.request("PATCH", self.url(path), data=data)
        return res["status"] == 204

    def make_order(self):
        for func in (self.login, self.get_foods, self.create_cart):
            if func():
                continue
            return False

        for i in range(random.randint(1, 3)):
            if not self.cart_add_food():
                return False

        data = {"cart_id": self.cart_id}
        res = self.request("POST", self.url("/orders"), data=data)
        if res["status"] == 200:
            return True
        return False


def job(host, port):
    q = Query(host, port)
    start = time.time()
    try:
        ok = q.make_order()
    except:
        if q.user_id:
            redis_store.sadd(USER_KEY, q.user_id)
        traceback.print_exc()
        redis_store.incr(FAILURE_KEY)
        return
    elapsed = time.time() - start

    if ok:
        redis_store.incr(SUCCESS_KEY)
        redis_store.lpush(RESPONSE_TIME_KEY, elapsed)
    else:
        if q.user_id:
            redis_store.sadd(USER_KEY, q.user_id)
        redis_store.incr(FAILURE_KEY)


def progress():
    prev = cur = 0
    delta = None
    try:
        while True:
            start = time.time()
            if delta is not None:
                redis_store.lpush(ORDER_EVERY_SEC_KEY, delta)
            time.sleep(1)
            elapsed = time.time() - start
            cur = get_value(SUCCESS_KEY)
            delta = int((cur - prev) / elapsed)
            prev = cur
            print("Finished orders:", delta)
    except KeyboardInterrupt:
        pass


def thread(host, port, threads, num):
    pool = ThreadPool(threads)
    for _ in range(num):
        pool.apply_async(job, (host, port))
    pool.close()
    pool.join()


def divide(n, m):
    """Divide integer n to m chunks
    """
    avg = int(n / m)
    remain = n - m * avg
    data = list(itertools.repeat(avg, m))
    for i in range(len(data)):
        if not remain:
            break
        data[i] += 1
        remain -= 1
    return data


def work(host, port, processes, threads, times):
    pool = Pool(processes,
                lambda: signal.signal(signal.SIGINT, signal.SIG_IGN))

    start = time.time()
    try:
        for chunk in divide(times, processes):
            pool.apply_async(thread, (host, port, threads, chunk))
        pool.close()

        t = Process(target=progress)
        t.daemon = True
        t.start()

        pool.join()
        t.terminate()
        t.join()
    except KeyboardInterrupt:
        pool.terminate()
        t.terminate()
        t.join()
        pool.join()
    elapsed = time.time() - start

    return elapsed


def get_value(key):
    v = redis_store.get(key)
    return 0 if v is None else int(v)


def get_range(key):
    v = redis_store.lrange(key, 0, -1)
    return [float(i) for i in v]


def safe_div(a, b):
    return a / b if b else 0


def report(processes, elapsed):
    success = get_value(SUCCESS_KEY)
    failure = get_value(FAILURE_KEY)
    requests = get_value(REQUEST_KEY)
    req_failed = get_value(REQUEST_FAILD_KEY)

    response_time = get_range(RESPONSE_TIME_KEY)
    request_time = get_range(REQUEST_TIME_KEY)
    order_sec = get_range(ORDER_EVERY_SEC_KEY)

    assert len(response_time) == success
    assert len(request_time) == requests

    total_time = float(sum(response_time))
    avg = safe_div(total_time, success)
    req_avg = safe_div(sum(request_time), float(requests))
    ops = safe_div(success, elapsed)
    qps = safe_div(requests, elapsed)
    mean_order = safe_div(sum(order_sec), len(order_sec))

    p = functools.partial(print, sep='')

    p("\nStats")
    p("Concurrenty Level:       ", processes)
    p("Time taken for tests:    ", round(elapsed * 1000, 2), "ms")
    p("Complete requests:       ", requests)
    p("Failed requests:         ", req_failed)
    p("Complete orders:         ", success)
    p("Failed orders:           ", failure)
    p("Time per request:        ", round(req_avg * 1000, 2), "ms", " (mean)")
    p("Time per order:          ", round(avg * 1000, 2), "ms", " (mean)")
    p("Request per second:      ", round(qps, 2))
    p("Order per second:        ", round(ops, 2))
    p("Orders for every second: ", int(max(order_sec)), " (max) ",
      int(min(order_sec)), " (min) ", int(mean_order), " (mean)")
    p()
    p("Percentage of orders made within a certain time (ms)")
    response_time = sorted(set(response_time)) if response_time else [0]
    l = len(response_time)
    for e in (0.5, 0.75, 0.8, 0.9, 0.95, 0.98, 1):
        idx = int(l * e)
        idx = 0 if idx == 0 else idx - 1
        p(" {:>4.0%}      ".format(e),
          int(math.ceil(response_time[idx] * 1000)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-H", "--host", default="localhost",
                        help="server host name")
    parser.add_argument("-p", "--port", default=8080, type=int,
                        help="server port")
    parser.add_argument("-c", "--processes", default=2, type=int,
                        help="processes")
    parser.add_argument("-t", "--threads", default=4, type=int,
                        help="threads")
    parser.add_argument("-n", "--num", default=10000, type=int,
                        help="requests")
    args = parser.parse_args()

    redis_store.delete(SUCCESS_KEY, FAILURE_KEY, RESPONSE_TIME_KEY,
                       REQUEST_FAILD_KEY, REQUEST_KEY, USER_KEY,
                       REQUEST_TIME_KEY, ORDER_EVERY_SEC_KEY)

    global users, foods
    users, foods = load_users(), load_foods()

    elapsed = work(args.host, args.port, args.processes, args.threads,
                   args.num)
    report(args.processes, elapsed)


if __name__ == "__main__":
    main()
