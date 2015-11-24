# -*- coding: utf-8 -*-

from conftest import food_store, json_get, token_gen


def test_foods():

    def _req():
        _, token = next(token_gen)
        return json_get("/foods", token)

    res = _req()
    assert res.status_code == 200

    foods = res.json()
    assert len(foods) == len(food_store) == 100

    foods2 = _req().json()
    assert foods == foods2

    for food in foods:
        assert food["id"] in food_store
        assert isinstance(food["stock"], int) and food["stock"] <= 1000
        assert isinstance(food["price"], int) and food["price"] > 0
        assert food_store[food["id"]]["price"] == food["price"]
