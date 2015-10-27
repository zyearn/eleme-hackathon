# -*- coding: utf-8 -*-

import requests


def test_foods(url, token):
    res = requests.get(url + "/foods", headers={"Access-Token": token})
    assert res.status_code == 200

    foods = res.json()
    assert len(foods) == 100

    food = foods[0]
    assert food["id"] > 0
    assert food["stock"] > 0
    assert food["price"] > 0
