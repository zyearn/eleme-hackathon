# Web Framework Benchmark

`GET /` calls redis to run the following lua script.

	local tot = 10
	for i = 1, tot, 1 do
	    redis.call('set', 'name:' .. tostring(i), i)
	end
	local sum = 0
	for i = 1, tot, 1 do
	    local str = redis.call('get', 'name:' .. tostring(i))
	    sum = sum + tostring(str)
	end
	return sum

use `ab -n 10000 -c 50 http://localhost:8080/` to benchmark. results are the followings (time per request, mean, across all concurrent requests):

	LANG    WEB         REDIS             METHOD      TIME
	---------------------------------------------------------
	python  tornado     redis-py          coroutine   1.406ms
	python  tornado     redis-py          sync        1.022ms
	python  aiohttp     asyncio-redis     coroutine   0.879ms
	python  falcon      redis-py          gunicorn    0.669ms
	node    express.js  node-redis        event       0.301ms
	golang  net/http    gopkg.in/redis.v3 coroutine   0.245ms