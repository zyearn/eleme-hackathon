# -*- coding: utf-8 -*-

from __future__ import absolute_import


from conftest import jpost


def test_new_carts(url, token):
    res = jpost(url + "/carts", token)
    assert res.status_code == 200
    assert len(res.json().get("cart_id", "")) > 0
