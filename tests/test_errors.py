# -*- coding: utf-8 -*-

import requests


def test_empty_request_error(url, username, password):
    res = requests.post(
        url + "/login",
        data=None,
        headers={"Content-type": "application/json"},
    )

    assert res.status_code == 400
    assert res.json().get("code") == "EMPTY_REQUEST"
    assert res.json().get("message") == u"请求体为空"


def test_malformed_json_error(url):
    res = requests.post(
        url + "/login",
        data="not a json request",
        headers={"Content-type": "application/json"},
    )
    assert res.status_code == 400
    assert res.json().get("code") == "MALFORMED_JSON"
    assert res.json().get("message") == u"格式错误"


def test_auth_error(url):
    res = requests.get(url + "/foods")

    assert res.status_code == 401
    assert res.json().get("code") == "INVALID_ACCESS_TOKEN"
    assert res.json().get("message") == u"无效的令牌"
