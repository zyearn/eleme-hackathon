#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from flask import Flask

host = os.getenv("APP_HOST", "localhost")
port = int(os.getenv("APP_PORT", "8080"))

app = Flask(__name__)


@app.route('/')
def hello_world():
    return 'Hello World!'

@app.route('/zz')
def dddd():
    return '123'

if __name__ == '__main__':
    app.run(host=host, port=port)
