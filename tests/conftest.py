# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging
logging.basicConfig(level=logging.WARNING)

import json
import os

import requests
import pytest
import pymysql
import pymysql.cursors


@pytest.fixture(scope="session")
def conf():
    """Try load local conf.json
    """
    fname = os.path.join(os.path.dirname(__file__), "conf.json")
    if os.path.exists(fname):
        with open(fname) as f:
            return json.load(f)


@pytest.fixture(scope="session")
def conn():
    return pymysql.connect(host=os.getenv("DB_HOST", "localhost"),
                           port=int(os.getenv("DB_PORT", 3306)),
                           user=os.getenv("DB_USER", "root"),
                           passwd=os.getenv("DB_PASS", "toor"),
                           db=os.getenv("DB_NAME", "eleme"),
                           cursorclass=pymysql.cursors.DictCursor,
                           autocommit=True)


@pytest.fixture(scope="session")
def url(conf):
    return conf.get("url")


@pytest.fixture(scope="session")
def username(conf):
    return conf.get("username")


@pytest.fixture(scope="session")
def password(conf):
    return conf.get("password")


@pytest.fixture(scope="session")
def get_token(url):
    def _f(username, password):
        data = {"username": username, "password": password}
        res = requests.post(
            url + "/login",
            data=json.dumps(data),
            headers={"Content-type": "application/json"},
        )
        assert res.status_code == 200
        return res.json()["access_token"]
    return _f


@pytest.fixture(scope="session")
def token(get_token, username, password):
    return get_token(username, password)


@pytest.fixture(scope="session")
def tokens(conn, get_token, username):
    users = []
    c = conn.cursor()
    c.execute("SELECT name, password FROM `user` "
              "WHERE name <> %s", (username,))
    users = c.fetchall()
    c.close()

    def _f():
        for u in users:
            yield get_token(u["name"], u["password"])
    return _f


@pytest.fixture(scope="session")
def price_of(conn):
    def _f(food_id):
        c = conn.cursor()
        c.execute("SELECT price FROM `food` where id = %s", (food_id))
        row = c.fetchone()
        c.close()
        return row["price"]
    return _f


@pytest.fixture(scope="session")
def stock_of(url, conn, token):
    def _f(food_id):
        res = jget(url + "/foods", token)
        assert res.status_code == 200
        foods = res.json()
        for f in foods:
            if f["id"] == food_id:
                return f["stock"]
        raise Exception("expected stock of food[%s] not found" % food_id)
    return _f


jget = lambda url, token: requests.get(
    url, headers={"Access-Token": token, "Content-type": "application/json"})

jpost = lambda url, token, data=None: requests.post(
    url,
    data=json.dumps(data),
    headers={"Access-Token": token, "Content-type": "application/json"}
)

jpatch = lambda url, token, data=None: requests.patch(
    url,
    data=json.dumps(data),
    headers={"Access-Token": token, "Content-type": "application/json"}
)
