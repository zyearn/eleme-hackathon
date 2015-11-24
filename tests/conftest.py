# -*- coding: utf-8 -*-

from __future__ import absolute_import

import collections
import json
import logging
import os
import random

import pymysql
import pymysql.cursors
import requests

logging.basicConfig(level=logging.WARNING)


# json conf
def _conf():
    """Try load local conf.json
    """
    fname = os.path.join(os.path.dirname(__file__), "conf.json")
    if os.path.exists(fname):
        with open(fname) as f:
            return json.load(f)


def _token(username, password):
    data = {"username": username, "password": password}
    res = requests.post(
        url + "/login",
        data=json.dumps(data),
        headers={"Content-type": "application/json"})
    assert res.status_code == 200
    return res.json()["access_token"]


# basic conf
conf = _conf()
url = conf["url"]

# admin info
admin_username = conf["username"]
admin_password = conf["password"]
admin_token = _token(admin_username, admin_password)

# mysql conn
conn = pymysql.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 3306)),
    user=os.getenv("DB_USER", "root"),
    passwd=os.getenv("DB_PASS", "toor"),
    db=os.getenv("DB_NAME", "eleme"),
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=True
)


def _load_users():
    c = conn.cursor()
    try:
        c.execute("SELECT id, name, password FROM `user` WHERE id > 1;")
        return {u["id"]: (u["name"], u["password"]) for u in c.fetchall()}
    finally:
        c.close()


def _load_foods():
    c = conn.cursor()
    try:
        c.execute("SELECT id, stock, price FROM `food`;")
        return {f["id"]: {"stock": f["stock"], "price": f["price"]}
                for f in c.fetchall()}
    finally:
        c.close()


# test data
user_store = _load_users()
food_store = _load_foods()
order_store = {}


# req utils
_session = requests.session()
_session.headers.update({"Content-type": "application/json"})


def json_get(path, tk):
    return _session.get(url + path, headers={"Access-Token": tk}, timeout=3)


def json_post(path, tk, data=None):
    return _session.post(
        url + path,
        json=data,
        headers={"Access-Token": tk},
        timeout=3)


def json_patch(path, tk, data):
    return _session.patch(
        url + path,
        json=data,
        headers={"Access-Token": tk},
        timeout=3)


def _token_gen():
    uids = list(user_store.keys())
    random.shuffle(uids)
    for uid in uids:
        yield uid, _token(*user_store[uid])
token_gen = _token_gen()


def _food_gen():
    food_ids = list(food_store.keys())
    while True:
        food_id = random.choice(food_ids)
        yield {"food_id": food_id, "count": 1}
food_gen = _food_gen()


# utils
def new_cart(token):
    res = json_post("/carts", token)
    return res.status_code == 200 and res.json()["cart_id"]


def make_order(uid, token, cart_id, food_items):
    for food_item in food_items:
        json_patch("/carts/%s" % cart_id, token, food_item)
    res = json_post("/orders", token, {"cart_id": cart_id})

    # decrease food stock, and record success order
    if res.status_code == 200:
        counts = collections.Counter()
        for food_item in food_items:
            counts[food_item["food_id"]] += food_item["count"]

        for food_id, count in counts.items():
            food_store[food_id]["stock"] -= count
        order_store[res.json()["id"]] = {"user_id": uid, "items": food_items}
    return res


def simple_make_order(food_items):
    uid, token = next(token_gen)
    return make_order(uid, token, new_cart(token), food_items)
