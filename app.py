#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from flask import Flask, request, jsonify
import pymysql
import pymysql.cursors
import json


host = os.getenv("APP_HOST", "localhost")
port = int(os.getenv("APP_PORT", "8080"))

app = Flask(__name__)

def conn():
    return pymysql.connect(host=os.getenv("DB_HOST", "localhost"),
                           port=int(os.getenv("DB_PORT", 3306)),
                           user=os.getenv("DB_USER", "root"),
                           passwd=os.getenv("DB_PASS", "toor"),
                           db=os.getenv("DB_NAME", "eleme"),
                           cursorclass=pymysql.cursors.DictCursor,
                           autocommit=True)

@app.route('/')
def hello_world():
    return 'Hello World!'

@app.route('/login', methods=['POST'])
def login():
    try:
        data = json.loads(request.data)
    except (ValueError, KeyError, TypeError) as error:
        print error
        return jsonify({'code':'MALFORMED_JSON', 'message':u'格式错误'}), 400

    if not bool(request.json):
        return jsonify({'code':'EMPTY_REQUEST', 'message':u'请求体为空'}), 400

    mysqlconn = conn()
    with mysqlconn.cursor() as cursor:
        sql = "select id, name from user where name=%s and password=%s"
        cursor.execute(sql, (request.json['username'], request.json['password']))
        result = cursor.fetchone()

    if bool(result):
        return jsonify({'user_id':result['id'], 'username':result['name'], 'access_token':'xxdabc'})
    else:
        return jsonify({'code':'USER_AUTH_FAIL', 'message':u'用户名或密码错误'}), 403


if __name__ == '__main__':
    app.debug=True
    app.run(host=host, port=port)
