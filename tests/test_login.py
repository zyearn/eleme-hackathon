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
    assert len(res.json().get("access_token", "")) == 32


def test_login_error_password(url, username):
    data = {"username": username, "password": "nottherightpassword"}
    res = requests.post(
        url + "/login",
        data=json.dumps(data),
        headers={"Content-type": "application/json"},
    )

    assert res.status_code == 403
    assert res.json().get("message") == "username or password incorrect"


def test_login_post_data(url, username, password):
    data = {"username": username, "password": password}
    res = requests.post(
        url + "/login",
        data=data,
        headers={"Content-type": "application/json"},
    )

    assert res.status_code == 753
    assert res.json().get("message") == "malformed json"
