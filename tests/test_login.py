# -*- coding: utf-8 -*-

import requests
import json


def test_login_success(url, username, password):
    data = {"username": username, "password": password}
    res = requests.post(
        url + "/login",
        data=json.dumps(data),
        headers={"Content-type": "application/json"},
    )
    assert res.status_code == 200
    assert len(res.json().get("access_token", "")) > 0


def test_login_error_password(url, username):
    data = {"username": username, "password": "nottherightpassword"}
    res = requests.post(
        url + "/login",
        data=json.dumps(data),
        headers={"Content-type": "application/json"},
    )

    assert res.status_code == 403
    assert res.json().get("code") == "USER_AUTH_FAIL"
    assert res.json().get("message") == u"用户名或密码错误"


def test_login_post_data(url, username, password):
    data = {"username": username, "password": password}
    res = requests.post(
        url + "/login",
        data=data,
        headers={"Content-type": "application/json"},
    )

    assert res.status_code == 400
    assert res.json().get("code") == "MALFORMED_JSON"
    assert res.json().get("message") == u"格式错误"
