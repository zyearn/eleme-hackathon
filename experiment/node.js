var express = require('express');
var redis = require("redis");
var client = redis.createClient();
var lua_func = null;

var app = express();

var script = "local tot = 10\n\
for i = 1, tot, 1 do\n\
    redis.call('set', 'node:' .. tostring(i), i)\n\
end\n\
local sum = 0\n\
for i = 1, tot, 1 do\n\
    local str = redis.call('get', 'node:' .. tostring(i))\n\
    sum = sum + tostring(str)\n\
end\n\
return sum";

client.on("error", function (err) {
    console.log("Error " + err);
});

client.script('load', script, function(err, sha) {
    if (err) throw err;
    lua_func = sha;
    app.get('/', function(req, res) {
        client.evalsha(lua_func, 0, function(err, sum) {
            if (err) throw err;
            res.send({result: sum});
        })
    });

    var server = app.listen(8080, function () {
        var host = server.address().address;
        var port = server.address().port;

        console.log('Example app listening at http://%s:%s', host, port);
    });

})

/*
Time per request:       15.045 [ms] (mean)
Time per request:       0.301 [ms] (mean, across all concurrent requests)
*/