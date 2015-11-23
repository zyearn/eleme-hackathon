# Eleme Hackathon Intro

饿了么 Hackathon 2015 初赛信息介绍。

活动及报名官网: http://hackathon.ele.me

本简介官方仓库: https://hackhub.ele.me/eleme/hackathon-intro


## 初赛赛题

使用 Python, Java, Go 三种语言（任选其一）实现一个“限时抢购”功能。

功能要求:

* 数据库中预设了 `food` 和 `user` 表。需要实现功能，让 `user` 表中的用户，购买 `food` 表中的食物。

* 每个用户只能下一次单。每张订单食物的总数不超过 3。用户可以有多个独立的购物车。

* 对实现方式，数据存储不作限制。但是需要保证最终一致性，通过下单接口返回成功的所有订单，必须和通过后台接口查询出来的订单一致。

* 应用必须可以被同等部署于 3 台服务器上，共同对外提供服务。

* 严格按照 `spec.md` 中的 API 规范编码，并通过所有单测。


## 开发流程

* 克隆本代码库，修改 `Vagrantfile` 并下载开发环境镜像。

* 参考 `spec.md` 文件中的 API 规范，编写基于 HTTP/Json 的 RESTful API。

* 编写 `app.yml` 并提供应用所需的语言环境和启动方式。

* 通过 `tests/` 中的所有单元测试。

* 通过 `benchmark/` 中的性能测试，并优化性能。


## 快速开始

为方便参赛选手快速开始编码，本次比赛预先提供了基于 vagrant + virtualbox 的各语言的开发环境镜像。

### 软件依赖

* Vagrant: [Vagrant Download](http://www.vagrantup.com/downloads)

* Virtualbox: [Virtualbox Download](https://www.virtualbox.org/wiki/Downloads)

### 基础代码库

克隆本仓库后，修改 `Vagrantfile`，取消对应语言的 box 注释，保存后执行 `vagrant up`，即可获得开发所需的一切环境。

各语言代码库示例:

* `python`: https://hackhub.ele.me/eleme/hackathon-py

* `java`: https://hackhub.ele.me/eleme/hackathon-java

* `go`: https://hackhub.ele.me/eleme/hackathon-go

开发环境内建 livereload 功能，当代码文件发生改变时，会自动重启应用。


## 环境介绍

基础环境基于 Ubuntu 14.04 LTS。

预装了 `mysql-server`, `redis-server`，并进行了端口映射，可直接通过 localhost 访问虚拟机里的 mysql, redis 和 app。详细可参考基础代码库中的 `Vagrantfile`。

执行 `vagrant ssh` 可登录虚拟机命令行，代码根目录已被挂载到虚拟机中的 `/vagrant` 路径下。

程序运行和重启日志会储存于代码根目录下的 `app.log`，可以使用 `tail -f app.log` 查看输出。

**注意事项**

环境中提供了以下环境变量: 

```
APP_HOST=0.0.0.0
APP_PORT=8080

DB_HOST=localhost
DB_PORT=3306
DB_NAME=eleme
DB_USER=root
DB_PASS=toor

REDIS_HOST=localhost
REDIS_PORT=6379

PYTHONPATH=/vagrant
GOPATH=/srv/gopath
JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64
```

请注意以下事项:

* 代码中对应的设置不要写死对应的值，而是根据环境变量获取。

* 不要更改对应的 PATH 信息。


### 工具脚本

虚拟机中提供了以下脚本:

* `gendata` (`/usr/local/bin/gendata`)

  此脚本用于初始化 mysql 表中预设的 `food` 表和 `user` 表。每次运行均会重新生成所有数据。
  表中的数据均为随机生成，实际进行单元测试和性能测试前，均会运行此脚本初始化数据。

* `launcher` (`/usr/local/bin/launcher`)

  此脚本可根据代码根目录下的 `app.yml` 文件启动应用。

* `hackathon-appreload` (`/usr/local/bin/launcher`)

  此脚本可监测代码文件的改动，并在有文件修改时，重新启动应用。
  应用启动日志，和应用输出均会被导出到代码根目录下的 `app.log` 文件。


虚拟机中提供了以下服务 (基于 upstart):

* `hackathon-app`

  此服务使用 `launcher` 运行应用。
  可执行 `sudo stop hackathon-app` 和  `sudo start hackathon-app` 来停止和开启应用。

* `hackathon-appreload`

  此服务提供 livereload app 功能。 当代码文件发生改动时，会尝试重启 `hackathon-app` 服务。


### 配置规范

应用通过在根目录下配置 `app.yml` 文件启动。配置文件包含两栏，`language` 和 `script`。

* `language` 必须是 py2, py3, pypy, go, java 中的一种。

* `script` 可以有多条命令，会依次执行。注意如果有一行 block 住了，会影响后续命令的执行。最后一行可以启动应用 server 并 block 住。


## 测试

测试分为两个部分，功能测试和性能测试。

### 功能测试

测试脚本基于 python 的 `pytest` 编写，可在基础代码库中运行 `make test` 来进行测试。

或者手动测试，示例:

```
cd tests

# run all tests
py.test

# run cart tests
py.test test_carts.py
```

代码提交至 gitlab 后，可通过 CI 来查看单测结果。 访问 http://hackhub-ci.ele.me 查看。


### 性能测试

性能测试基于腾讯云。

* 代码会镜像部署在 3 台 2CPU - 4GB 服务器上。

* Redis 和 MySQL 各提供一台。和应用服务器独立。

* 测试脚本会以模拟 1000 并发，以 round robin 的负载均衡策略均衡的请求 3 台服务器。

* 脚本模拟基础用户下单流程，最终成绩以每秒成功订单数为准。

请注意代码中对应的环境变量，不要写死对应的值，而是根据环境变量获取。


### 排名

最终排名和成绩，以最后一天公布的排行榜为基准。

之后会封存代码，进入代码 review 阶段。有任何主观作弊行为的，将取消资格，名额顺延。

请注意以下事项：

* 请勿使用任何主观 cheat 代码。（此条没有固定的评定标准，判定依据为 review 代码的人认为你在 cheat。如发生争议，可在赛后联系饿了么公开相关代码和判定原因。）

* 请勿运行任何非源码 build 生成的二进制文件。

* 确保成绩中记录的 commit 存在于代码库中。

* 确保代码和成绩真实，可重现，可追溯。
