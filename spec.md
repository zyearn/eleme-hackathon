# 接口规范

需要实现基于 HTTP/JSON 的 RESTful API，至少包含以下接口:

1. <a href="#login">登录</a>
1. <a href="#foods">查询库存</a>
1. <a href="#carts">创建篮子</a>
1. <a href="#food">添加食物</a>
1. <a href="#order">下单</a>
1. <a href="#orders">查询订单</a>
1. <a href="#admin-orders">后台接口－查询订单</a>

除登录接口外，其他接口需要传入登录接口得到的 access_token，access_token 无效或者为空会直接返回401异常：

```
401 Unauthorized
{
    "code": "INVALID_ACCESS_TOKEN",
    "message": "无效的令牌"
}
```

其中后台接口只有用 root 用户登录后的 access_token 才能访问。

其中 access_token 需要支持： parameter 和 http header 两种认证方式。客户端提供其中一个即可通过认证。

```
# by parameter
GET /foods?access_token=xxx

# by http header
GET /foods Access-Token:xxx
```


如果需要传参的接口，传过来的 body 为空。则返回400异常:

```
400 Bad Request
{
    "code": "EMPTY_REQUEST",
    "message": "请求体为空"
}
```

如果需要传参的接口，传过来的请求体 json 格式有误。则返回 400 异常:

```
400 Bad Request
{
    "code": "MALFORMED_JSON",
    "message": "格式错误"
}
```

<a name="login" />

## 登录

`POST /login`

##### 请求体

参数名 | 类型 | 描述
---|---|---
username | string | 用户名
password | string | 密码

#### 请求示例

```
POST /login
{
    "username": "robot",
    "password": "robot"
}
```

#### 响应示例

```
200 OK
{
    "user_id": 1,
    "username": "robot",
    "access_token": "xxx"
}
```

#### 异常示例

用户名不存在或者密码错误：

```
403 Forbidden
{
    "code": "USER_AUTH_FAIL",
    "message": "用户名或密码错误"
}
```

<a name="foods" />
## 查询库存

`GET /foods`

#### 请求示例

```
GET /foods?access_token=xxx
```

#### 响应示例

```
200 OK
[
    {"id": 1, "price": 12, "stock": 99},
    {"id": 2, "price": 10, "stock": 89},
    {"id": 3, "price": 22, "stock": 91}
]
```

<a name="carts" />
## 创建篮子

`POST /carts`

#### 请求示例

```
POST /carts?access_token=xxx

```

#### 响应示例

```
200 OK
{
    "cart_id ": "e0c68eb96bd8495dbb8fcd8e86fc48a3"
}
```

<a name="food" />
## 添加食物

`PATCH /carts/:cart_id`

##### 请求体

参数名 | 类型 | 描述
---|---|---
food_id | int | 添加的食物id
count | int | 添加的食物数量

#### 请求示例

```
PATCH /carts/e0c68eb96bd8495dbb8fcd8e86fc48a3?access_token=xxx
{
    "food_id": 2,
    "count": 1
}
```

#### 响应示例

```
204 No content
```

#### 异常示例

篮子不存在：

```
404 Not Found
{
    "code": "CART_NOT_FOUND",
    "message": "篮子不存在"
}
```

篮子不属于当前用户：

```
401 Unauthorized
{
    "code": "NOT_AUTHORIZED_TO_ACCESS_CART",
    "message": "无权限访问指定的篮子"
}
```

食物数量超过篮子最大限制：

```
403 Forbidden
{
    "code": "FOOD_OUT_OF_LIMIT",
    "message": "篮子中食物数量超过了三个"
}
```

食物不存在：

```
404 Not Found
{
    "code": "FOOD_NOT_FOUND",
    "message": "食物不存在"
}
```

<a name="order" />
## 下单

`POST /orders`

##### 请求体

参数名 | 类型 | 描述
---|---|---
cart_id | string | 篮子id

#### 请求示例

```
POST /orders?access_token=xxx
{
    "cart_id": "e0c68eb96bd8495dbb8fcd8e86fc48a3"
}
```

#### 响应示例

```
200 OK
{
    "id ": "someorderid"
}
```

#### 异常示例

篮子不存在

```
404 Not Found
{
    "code": "CART_NOT_FOUND",
    "message": "篮子不存在"
}
```

篮子不属于当前用户

```
403 Forbidden
{
    "code": "NOT_AUTHORIZED_TO_ACCESS_CART",
    "message": "无权限访问指定的篮子"
}
```

食物库存不足：

```
403 Forbidden
{
    "code": "FOOD_OUT_OF_STOCK",
    "message": "食物库存不足"
}
```

超过下单次数限制

```
403 Forbidden
{
    "code": "ORDER_OUT_OF_LIMIT",
    "message": "每个用户只能下一单"
}
```

<a name="orders" />
## 查询订单
`GET /orders`

#### 请求示例

```
GET /orders?access_token=xxx
```

#### 响应示例

```
200 OK
[
    {
        "id": "someorderid",
        "items": [
            {"food_id": 2, "count": 1}
        ],
        "total": 10
    }
]
```


<a name="admin-orders" />
## 后台接口－查询订单
`GET /admin/orders`

#### 请求示例

```
GET /admin/orders?access_token=xxx
```

#### 响应示例

```
200 OK
[
    {
        "id": "someorderid",
        "user_id": 1,
        "items": [
            {"food_id": 2, "count": 1}
        ],
        "total": 10
    }
]
```

