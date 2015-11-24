#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import argparse
import collections
import contextlib
import functools
import itertools
import json
import math
import os
import random
import signal
import time

import redis
import pymysql


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

USER_KEY = "{}:user".format(KEY_PREFIX)

SUCCESS_KEY = "{}:success".format(KEY_PREFIX)
FAILURE_KEY = "{}:failure".format(KEY_PREFIX)

ORDER_RESP_TIME_KEY = "{}:order_resp_time".format(KEY_PREFIX)
REQ_RESP_TIME_KEY = "{}:req_resp_time".format(KEY_PREFIX)

REQUEST_SUCCESS_KEY = "{}:request_success".format(KEY_PREFIX)
REQUEST_FAILURE_KEY = "{}:request_failure".format(KEY_PREFIX)

REQ_FINISH_TIME_KEY = "{}:req_finish_time".format(KEY_PREFIX)
ORDER_FINISH_TIME_KEY = "{}:order_finish_time".format(KEY_PREFIX)

redis_store = redis.Redis()
users, foods = {}, []


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
    global users
    with db_query() as db:
        cur = db.cursor()

        # load users
        cur.execute("SELECT id, name, password FROM user")

        for i, name, pw in cur.fetchall():
            users[i] = {"username": name, "password": pw}
    redis_store.sadd(USER_KEY, *users.keys())
    return users


def load_foods():
    global foods
    with db_query() as db:
        cur = db.cursor()
        cur.execute("SELECT id, stock, price FROM food")

        for i, stock, price in cur.fetchall():
            foods.append({"id": i, "stock": stock})
    return foods


def safe_loads(data):
    try:
        return json.loads(data)
    except:
        return data


class QueryException(Exception):

    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return "{} {}".format(self.code, self.message)


class Query(object):

    __slots__ = ["access_token", "user_id", "cart_id", "client"]

    def __init__(self, host, port):
        self.client = httplib.HTTPConnection(host, port, timeout=3)

        self.access_token = None
        self.user_id = None
        self.cart_id = None

    def request(self, method, url, headers=None, data=None):
        data = data or {}
        headers = headers or {}
        headers["Content-Type"] = "application/json"

        start = time.time()
        status = None
        try:
            self.client.request(method, url, body=json.dumps(data),
                                headers=headers)
            response = self.client.getresponse()
            status = response.status
            data = response.read().decode("utf-8")
            self.client.close()
            return {"status": status, "data": safe_loads(data)}
        finally:
            now = time.time()
            elapsed = now - start

            with redis_store.pipeline() as p:
                if status in (200, 204):
                    p.incr(REQUEST_SUCCESS_KEY)
                    p.lpush(REQ_FINISH_TIME_KEY, now)
                else:
                    p.incr(REQUEST_FAILURE_KEY)
                p.lpush(REQ_RESP_TIME_KEY, elapsed)
                p.execute()

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
        if not user_id:
            return False

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
        except:
            return False
        return response["status"] == 200

    def cart_add_food(self):
        food = random.choice(foods)
        data = {"food_id": food["id"], "count": 1}
        path = "/carts/{}".format(self.cart_id)
        res = self.request("PATCH", self.url(path), data=data)
        return res["status"] == 204

    def make_order(self):
        chain = [self.login, self.get_foods, self.create_cart,
                 self.cart_add_food, self.cart_add_food]
        for action in chain:
            if not action():
                return False

        data = {"cart_id": self.cart_id}
        res = self.request("POST", self.url("/orders"), data=data)
        return res["status"] == 200


def job(host, port):
    q = Query(host, port)

    start = time.time()
    try:
        ok = q.make_order()
    except:
        ok = False

    end = time.time()
    elapsed = end - start

    with redis_store.pipeline() as p:
        if ok:
            p.incr(SUCCESS_KEY)
            p.lpush(ORDER_FINISH_TIME_KEY, end)
        else:
            p.incr(FAILURE_KEY)
        p.lpush(ORDER_RESP_TIME_KEY, elapsed)
        p.execute()


def progress():
    try:
        prev = 0
        while True:
            time.sleep(1)
            cur = get_value(SUCCESS_KEY)

            msg = "Orders Per Second: {:4d}/s".format(cur - prev)
            print(msg, end='')
            print('\r' * len(msg), end='')

            prev = cur

    except KeyboardInterrupt:
        pass
    finally:
        print('\n')


def thread(host, port, threads, num):
    pool = ThreadPool(threads)
    for _ in range(num):
        pool.apply_async(job, (host, port))
        time.sleep(0.001)
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
    p = Process(target=progress)
    p.daemon = True

    start = time.time()

    try:
        for chunk in divide(times, processes):
            pool.apply_async(thread, (host, port, threads, chunk))

        p.start()

        pool.close()
        pool.join()
        p.terminate()
        p.join()

    except KeyboardInterrupt:
        pool.terminate()
        p.terminate()
        p.join()
        pool.join()

    return time.time() - start


def get_value(key):
    v = redis_store.get(key)
    return 0 if v is None else int(v)


def get_range(key):
    v = redis_store.lrange(key, 0, -1)
    return [float(i) for i in v]


def safe_div(a, b):
    return a / b if b else 0


def get_avg(l):
    return safe_div(sum(l), float(len(l)))


def report(processes, threads, total_time, total_order):
    success = get_value(SUCCESS_KEY)
    failure = get_value(FAILURE_KEY)
    req_success = get_value(REQUEST_SUCCESS_KEY)
    req_failure = get_value(REQUEST_FAILURE_KEY)

    req_resp_time = get_range(REQ_RESP_TIME_KEY)
    order_resp_time = get_range(ORDER_RESP_TIME_KEY)
    req_finish_time = get_range(REQ_FINISH_TIME_KEY)
    order_finish_time = get_range(ORDER_FINISH_TIME_KEY)

    assert len(order_resp_time) == success + failure
    assert len(req_resp_time) == req_success + req_failure

    req_avg = safe_div(sum(req_resp_time), float(req_success))
    order_avg = safe_div(sum(order_resp_time), success)

    req_sec = collections.Counter(int(t) for t in req_finish_time)
    order_sec = collections.Counter(int(t) for t in order_finish_time)

    # remove the highest and lowest score
    stats_req_sec = sorted(req_sec.values())[1:-1]
    max_req_sec = int(get_avg(stats_req_sec[-5:]))
    min_req_sec = int(get_avg(stats_req_sec[:5]))
    mean_req_sec = int(get_avg(stats_req_sec))

    # remove the highest and lowest score
    stats_order_sec = sorted(order_sec.values())[1:-1]
    max_order_sec = int(get_avg(stats_order_sec[-5:]))
    min_order_sec = int(get_avg(stats_order_sec[:5]))
    mean_order_sec = int(get_avg(stats_order_sec))

    p = functools.partial(print, sep='')

    p("Score:                ", max_order_sec)
    p("Correct Rate:         ", round(success / total_order * 100, 2), "%")

    p("\nStats")
    p("Concurrent Level:     ", processes, " x ", threads)
    p("Time taken for tests: ", round(total_time * 1000, 2), "ms")
    p("Complete requests:    ", req_success)
    p("Failed requests:      ", req_failure)
    p("Complete orders:      ", success)
    p("Failed orders:        ", failure)
    p("Time per request:     ", round(req_avg * 1000, 2), "ms", " (mean)")
    p("Time per order:       ", round(order_avg * 1000, 2), "ms", " (mean)")
    p("Request per second:   ", max_req_sec, " (max) ", min_req_sec, " (min) ", mean_req_sec, " (mean)")  # noqa
    p("Order per second:     ", max_order_sec, " (max) ", min_order_sec, " (min) ", mean_order_sec, " (mean)")  # noqa

    p("\nPercentage of orders made within a certain time (ms)")
    order_resp_time = sorted(set(order_resp_time)) if order_resp_time else [0]
    l = len(order_resp_time)
    for e in (0.5, 0.75, 0.8, 0.9, 0.95, 0.98, 1):
        idx = int(l * e)
        idx = 0 if idx == 0 else idx - 1
        p(" {:>4.0%}      ".format(e),
          int(math.ceil(order_resp_time[idx] * 1000)))


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

    redis_store.delete(
        USER_KEY, SUCCESS_KEY, FAILURE_KEY,
        ORDER_RESP_TIME_KEY, REQ_RESP_TIME_KEY,
        REQUEST_SUCCESS_KEY, REQUEST_FAILURE_KEY,
        REQ_FINISH_TIME_KEY, ORDER_FINISH_TIME_KEY)

    load_users()
    load_foods()

    total_time = work(
        args.host, args.port, args.processes, args.threads, args.num)

    report(args.processes, args.threads, total_time, float(args.num))


if __name__ == "__main__":
    main()
