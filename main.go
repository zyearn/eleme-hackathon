// Go hello-world implementation for eleme/hackathon.

package main

import (
	"fmt"
	"net/http"
	"os"
    "./src/model"
)

func main() {
    model.Sync_redis_from_mysql()
	host := os.Getenv("APP_HOST")
	port := os.Getenv("APP_PORT")
	if host == "" {
		host = "localhost"
	}
	if port == "" {
		port = "8080"
	}
	addr := fmt.Sprintf("%s:%s", host, port)
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("hello world!"))
	})
	http.ListenAndServe(addr, nil)
}
