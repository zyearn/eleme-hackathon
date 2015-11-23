# -*- coding: utf-8 -*-

import random

import concurrent.futures
from concurrent.futures.thread import ThreadPoolExecutor

from conftest import (
    admin_token,
    food_store,
    json_get,
    order_store,
    simple_make_order,
    token_gen, new_cart, json_patch, json_post)


def buy_to_stock(food_id, target_stock):
    remain_stock = max(food_store[food_id]["stock"] - target_stock, 0)
    while remain_stock > 0:
        count = min(remain_stock, 3)
        res = simple_make_order([{"food_id": food_id, "count": count}])

        # should success when food have remain stock
        assert res.status_code == 200

        remain_stock -= count


def test_food_stock_consistency():

    food_id = random.choice(list(food_store.keys()))
    buy_to_stock(food_id, 0)

    # should fail when food out of stock
    res = simple_make_order([{"food_id": food_id, "count": 1}])
    assert res.status_code == 403
    assert res.json() == {"code": "FOOD_OUT_OF_STOCK",
                          "message": u"食物库存不足"}


def test_admin_query_orders():
    res = json_get("/admin/orders", admin_token)
    assert res.status_code == 200

    q_orders = res.json()
    assert len(q_orders) == len(order_store)

    for q_order in q_orders:
        order_id = q_order["id"]
        assert order_id in order_store
        assert q_order["user_id"] == order_store[order_id]["user_id"]
        assert q_order["items"] == order_store[order_id]["items"]


def test_food_not_oversold_under_concurrent():

    TEST_FOOD_COUNT = 5
    TEST_FOOD_STOCK = 10

    # random choose foods with more than 10 stock
    test_food_ids = random.sample(
        [f for f, s in food_store.items() if s["stock"] >= TEST_FOOD_STOCK],
        TEST_FOOD_COUNT)
    for food_id in test_food_ids:
        buy_to_stock(food_id, TEST_FOOD_STOCK)
        assert food_store[food_id]["stock"] == TEST_FOOD_STOCK

    # enumerate all food items
    total_food_items = []
    for food_id in test_food_ids:
        remain_stock = food_store[food_id]["stock"]
        items = [{"food_id": food_id, "count": 1}] * remain_stock
        total_food_items.extend(items)
    assert len(total_food_items) == TEST_FOOD_COUNT * TEST_FOOD_STOCK

    # try to buy as much as twice of the stock
    test_food_items = total_food_items * 2
    random.shuffle(test_food_items)

    # prepare carts & tokens, each carts contains 2 foods
    cart_ids, tokens, items_list = [], [], []
    for food_items in zip(test_food_items[::2], test_food_items[1::2]):
        _, token = next(token_gen)
        cart_id = new_cart(token)

        for item in food_items:
            res = json_patch("/carts/%s" % cart_id, token, item)
            assert res.status_code == 204

        cart_ids.append(cart_id)
        tokens.append(token)
        items_list.append(food_items)

    def _make(cart_id, token, food_items):
        res = json_post("/orders", token, {"cart_id": cart_id})
        if res.status_code == 200:
            for food_item in food_items:
                food_store[food_item["food_id"]]["stock"] -= 1
        return res

    # make order with prepared carts, using 3 concurrent threads
    # allow sell slower (remain stock > 0)
    # best sell all and correct (remain stock == 0)
    # disallow oversold (remain stock < 0)
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_results = [
            executor.submit(_make, ct, tk, fs)
            for ct, tk, fs in zip(cart_ids, tokens, items_list)]
        concurrent.futures.wait(future_results, timeout=30)

    # test not oversold
    for food_id in test_food_ids:
        # print("stock %s -> %s" % (food_id, food_store[food_id]["stock"]))
        assert food_store[food_id]["stock"] >= 0
