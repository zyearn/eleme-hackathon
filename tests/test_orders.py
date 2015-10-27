# -*- coding: utf-8 -*-

from __future__ import absolute_import
import random

import pytest

from conftest import jget, jpost, jpatch

items = {"food_id": 1, "count": 2}


@pytest.fixture
def make_order(url):
    def _f(token, _items=None):
        res = jpost(url + "/carts", token)
        cart_id = res.json()["cart_id"]
        jpatch(url + "/carts/%s" % cart_id, token, _items or items)

        res = jpost(url + "/orders", token, {"cart_id": cart_id})
        return res
    return _f


@pytest.fixture(scope="function")
def cart_id(url, token):
    res = jpost(url + "/carts", token)
    return res.status_code == 200 and res.json()["cart_id"]


def test_get_orders(url, new_token):
    token = new_token().next()
    res = jget(url + "/orders", token)
    assert res.status_code == 200
    assert len(res.json()) == 0


def test_add_food_success(url, token, cart_id):
    food_count = {"food_id": 2, "count": 1}
    res = jpatch(url + "/carts/%s" % cart_id, token, food_count)
    assert res.status_code == 204
    assert len(res.content) == 0

    # silent ignore foods delete errors
    food_count = {"food_id": 2, "count": -1}
    res = jpatch(url + "/carts/%s" % cart_id, token, food_count)
    assert res.status_code == 204
    assert len(res.content) == 0


def test_del_food_success(url, token, cart_id):
    # silent ignore foods delete errors
    food_count = {"food_id": 2, "count": -2}
    res = jpatch(url + "/carts/%s" % cart_id, token, food_count)
    assert res.status_code == 204

    food_count = {"food_id": 3, "count": -2}
    res = jpatch(url + "/carts/%s" % cart_id, token, food_count)
    assert res.status_code == 204


def test_add_food_exceed_limit_error(url, token, cart_id):
    food_count = {"food_id": 2, "count": 4}
    res = jpatch(url + "/carts/%s" % cart_id, token, food_count)
    assert res.status_code == 403
    assert res.json()["message"] == "food count exceed maximum limit"


def test_add_food_not_exists_error(url, token, cart_id):
    food_count = {"food_id": -1, "count": 2}
    res = jpatch(url + "/carts/%s" % cart_id, token, food_count)
    assert res.status_code == 404
    print(res.json())
    assert res.json()["message"] == "food not exists"


def test_make_order_success(make_order, token):
    res = make_order(token)
    assert res.status_code == 200
    assert len(res.json()["id"]) > 0


def test_order_consistency(url, new_token, make_order, price_of):
    token = new_token().next()
    make_order(token)

    res = jget(url + "/orders", token)
    order = res.json()[0]

    assert (order["id"]) > 0
    assert len(order["items"]) == 1
    o = order["items"]
    assert o["food_id"] == items["food_id"]
    assert o["count"] == items["count"]
    assert order["total"] > price_of(items["food_id"]) * items["count"]


def test_order_food_consistency(new_token, make_order, stock_of):
    food_id = 42
    stock = stock_of(food_id)
    user_count = random.randint(1, stock / 2)
    for _ in range(user_count):
        token = new_token().next()
        make_order(token, {"food_id": food_id, "count": 2})
    assert stock_of(food_id) == stock - user_count * 2


def test_make_order_exceed_limit_error(make_order, new_token):
    token = new_token().next()
    make_order(token)
    res = make_order(token)
    assert res.status_code == 403
    assert res.json()["message"] == "order count exceed maximum limit"


def test_make_order_error(url, token):
    cart_id = "notrealcartid"
    res = jpost(url + "/orders", token, {"cart_id": cart_id})
    assert res.status_code == 401
    assert res.json()["message"] == "cart not owned by user"
