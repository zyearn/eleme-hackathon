# -*- coding: utf-8 -*-

import requests


def test_empty_request_error(url, username, password):
    res = requests.post(
        url + "/login",
        data=None,
        headers={"Content-type": "application/json"},
    )

    assert res.status_code == 400
    assert res.json().get("message") == "empty request"


def test_malformed_json_error(url):
    res = requests.post(
        url + "/login",
        data="not a json request",
        headers={"Content-type": "application/json"},
    )
    assert res.status_code == 753
    assert res.json().get("message") == "malformed json"


def test_auth_error(url):
    res = requests.get(url + "/foods")

    assert res.status_code == 401
    assert res.json().get("message") == "invalid access token"
