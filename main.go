// Go hello-world implementation for eleme/hackathon.

package main

import (
	"./src/model"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"

	"github.com/ant0ine/go-json-rest/rest"
	"github.com/bitly/go-simplejson"
)

func TokenChecker(r *rest.Request) (int, string) {
	t1 := r.Header.Get("Access-Token")
	t2 := r.URL.Query().Get("Access-Token")

	var token string
	if t1 != "" {
		token = t1
	} else if t2 != "" {
		token = t2
	} else {
		return -1, ""
	}

	if model.Is_token_exist(token) {
		fmt.Println("token exist")
		return 0, token
	}

	fmt.Println("token not exist")
	return -1, ""
}

func Index(w rest.ResponseWriter, r *rest.Request) {
	w.WriteJson(map[string]string{"Body": "Hello World!"})
}

func Login(w rest.ResponseWriter, r *rest.Request) {
	//TokenChecker(r)
	var data interface{}
	rtn := parse_request_body(r, &data)
	if rtn == 0 {
		byte_json, _ := json.Marshal(data)
		user_info, _ := simplejson.NewJson(byte_json)
		username, _ := user_info.Get("username").String()
		password, _ := user_info.Get("password").String()
		rtn, user_id, token := model.PostLogin(username, password)

		if rtn == 0 {
			w.WriteJson(map[string]string{"user_id": user_id, "username": username, "access_token": token})
		} else {
			w.WriteHeader(http.StatusForbidden)
			w.WriteJson(map[string]string{"code": "USER_AUTH_FAIL", "message": "用户名或密码错误"})
		}
	} else if rtn == -1 {
		// EOF
		w.WriteHeader(http.StatusBadRequest)
		w.WriteJson(map[string]string{"code": "EMPTY_REQUEST", "message": "请求体为空"})
	} else {
		w.WriteHeader(http.StatusBadRequest)
		w.WriteJson(map[string]string{"code": "MALFORMED_JSON", "message": "格式错误"})
	}
}

func Foods(w rest.ResponseWriter, r *rest.Request) {
	rtn, _ := TokenChecker(r)
	if rtn < 0 {
		w.WriteHeader(http.StatusUnauthorized)
		w.WriteJson(map[string]string{"code": "INVALID_ACCESS_TOKEN", "message": "无效的令牌"})
		return
	}

	model.Get_foods()
	food_info, _ := simplejson.NewJson([]byte(`[{"id": 1,"price": 12, "stock": 99}, {"id":1}]`))
	w.WriteJson(food_info)
}

/* Util function */
func parse_request_body(r *rest.Request, data *interface{}) int {
	err := json.NewDecoder(r.Body).Decode(data)
	switch {
	case err == io.EOF:
		return -1
	case err != nil:
		return -2
	}

	return 0
}

/* Util function */
func main() {
	model.Sync_redis_from_mysql()
	fmt.Println("server started")

	host := os.Getenv("APP_HOST")
	port := os.Getenv("APP_PORT")
	if host == "" {
		host = "localhost"
	}
	if port == "" {
		port = "8080"
	}
	addr := fmt.Sprintf("%s:%s", host, port)

	api := rest.NewApi()
	api.Use(rest.DefaultDevStack...)
	router, err := rest.MakeRouter(
		rest.Get("/", Index),
		rest.Post("/login", Login),
		rest.Get("/foods", Foods),
	)
	if err != nil {
		log.Fatal(err)
	}
	api.SetApp(router)

	log.Fatal(http.ListenAndServe(addr, api.MakeHandler()))
}
