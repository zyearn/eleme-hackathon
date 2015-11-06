# -*- coding: utf-8 -*-

from __future__ import absolute_import

import pytest

from conftest import jget, jpost, jpatch

items = {"food_id": 1, "count": 2}


@pytest.fixture
def make_order(url):
    def _f(token, _items=None):
        res = jpost(url + "/carts", token)
        cart_id = res.json()["cart_id"]
        jpatch(url + "/carts/%s" % cart_id, token, _items or items)
        return jpost(url + "/orders", token, {"cart_id": cart_id})
    return _f


@pytest.fixture(scope="function")
def cart_id(url, token):
    res = jpost(url + "/carts", token)
    return res.status_code == 200 and res.json()["cart_id"]


def test_get_orders(url, token):
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


def test_add_food_error(url, token):
    res = jpatch(url + "/carts/-1", token, items)
    assert res.status_code == 404
    assert res.json()["code"] == "CART_NOT_FOUND"
    assert res.json()["message"] == u"篮子不存在"


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
    assert res.json()["code"] == "FOOD_OUT_OF_LIMIT"
    assert res.json()["message"] == u"篮子中食物数量超过了三个"


def test_add_food_not_exists_error(url, token, cart_id):
    food_count = {"food_id": -1, "count": 2}
    res = jpatch(url + "/carts/%s" % cart_id, token, food_count)
    assert res.status_code == 404
    assert res.json()["code"] == "FOOD_NOT_FOUND"
    assert res.json()["message"] == u"食物不存在"


def test_make_order(url, token, make_order, price_of):
    # make order success
    res = make_order(token)
    assert res.status_code == 200
    assert len(res.json()["id"]) > 0

    # verify query return the same order
    order, = jget(url + "/orders", token).json()
    assert len(order["id"]) > 0
    assert len(order["items"]) == 1

    food, = order["items"]
    assert food["food_id"] == items["food_id"]
    assert food["count"] == items["count"]
    assert order["total"] == sum(price_of(item["food_id"]) * item["count"]
                                 for item in order["items"])

    # test only 1 order can be made
    res = make_order(token)
    assert res.status_code == 403
    assert res.json()["code"] == "ORDER_OUT_OF_LIMIT"
    assert res.json()["message"] == u"每个用户只能下一单"


def test_food_stock_consistency(tokens, make_order, stock_of):
    token_gen = tokens()

    # should able to make order when there's remain of food stock
    food_id = 42
    remain_stock = stock_of(food_id)
    for token in token_gen:
        count = min(remain_stock, 3)
        res = make_order(token, {"food_id": food_id, "count": count})
        remain_stock -= count

        if remain_stock == 0:
            break

    res = make_order(next(token_gen), {"food_id": food_id, "count": 1})
    assert res.status_code == 403
    assert res.json()["code"] == "FOOD_OUT_OF_STOCK"
    assert res.json()["message"] == u"食物库存不足"
