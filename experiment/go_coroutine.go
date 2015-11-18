package main

import (
    "fmt"
    "net/http"
    "gopkg.in/redis.v3"
)

const script = `
local tot = 10
for i = 1, tot, 1 do
    redis.call('set', 'go:' .. tostring(i), i)
end
local sum = 0
for i = 1, tot, 1 do
    local str = redis.call('get', 'go:' .. tostring(i))
    sum = sum + tostring(str)
end
return sum
`
var client *redis.Client
var lua_func *redis.Script

func handler(w http.ResponseWriter, r *http.Request) {
    sum := lua_func.Run(client, []string{}, []string{}).String()
    fmt.Fprintf(w, "%s", sum)
}

func main() {
    client = redis.NewClient(&redis.Options{
        Addr:     "localhost:6379",
        Password: "", // no password set
        DB:       0,  // use default DB
    })

    lua_func = redis.NewScript(script)

    http.HandleFunc("/", handler)
    http.ListenAndServe(":8080", nil)
}

// Time per request:       12.263 [ms] (mean)
// Time per request:       0.245 [ms] (mean, across all concurrent requests)