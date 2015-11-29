// Go hello-world implementation for eleme/hackathon.

package main

import (
	"./src/model"
	"encoding/json"
	"fmt"
	"github.com/ant0ine/go-json-rest/rest"
	"github.com/bitly/go-simplejson"
	"io"
	"log"
	"net/http"
	"os"
	"runtime"
	"strconv"
)

func TokenChecker(r *rest.Request) (int, string) {
	t1 := r.Header.Get("Access-Token")
	t2 := r.URL.Query().Get("access_token")

	var token string
	if t1 != "" {
		token = t1
	} else if t2 != "" {
		token = t2
	} else {
		return -1, ""
	}

	if model.Is_token_exist(token) {
		//fmt.Println("token exist")
		return 0, token
	}

	//fmt.Println("token not exist")
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
			w.(http.ResponseWriter).Write([]byte(
				` {"user_id": ` +
					strconv.Itoa(user_id) +
					`, "username": ` +
					`"` + username + `"` +
					`, "access_token": ` +
					`"` + token + `"` +
					`}`))
		} else {
			w.WriteHeader(http.StatusForbidden)
			w.(http.ResponseWriter).Write([]byte(` {"code": "USER_AUTH_FAIL", "message": "用户名或密码错误"}`))
		}
	} else if rtn == -1 {
		// EOF
		w.WriteHeader(http.StatusBadRequest)
		w.(http.ResponseWriter).Write([]byte(`{"code": "EMPTY_REQUEST", "message": "请求体为空"}`))
	} else {
		w.WriteHeader(http.StatusBadRequest)
		w.(http.ResponseWriter).Write([]byte(`{"code": "MALFORMED_JSON", "message": "格式错误"}`))
	}
}

func Foods(w rest.ResponseWriter, r *rest.Request) {
	rtn, _ := TokenChecker(r)
	if rtn < 0 {
		w.WriteHeader(http.StatusUnauthorized)
		w.(http.ResponseWriter).Write([]byte(`{"code": "INVALID_ACCESS_TOKEN", "message": "无效的令牌"}`))
		return
	}
	res := model.Get_foods()
	w.(http.ResponseWriter).Write(res)

}

func Post_carts(w rest.ResponseWriter, r *rest.Request) {
	rtn, token := TokenChecker(r)
	if rtn < 0 {
		w.WriteHeader(http.StatusUnauthorized)
		w.(http.ResponseWriter).Write([]byte(`{"code": "INVALID_ACCESS_TOKEN", "message": "无效的令牌"}`))
		return
	}

	cartid := model.Create_cart(token)
	//w.WriteJson(map[string]string{"cart_id": cartid})
	w.(http.ResponseWriter).Write([]byte(`{"cart_id":"` + cartid + `"}`))
}

func Patch_carts(w rest.ResponseWriter, r *rest.Request) {
	rtn, token := TokenChecker(r)
	cartid := r.PathParam("cartid")

	//model.L.Print("cartid is ", cartid)
	var data interface{}
	rtn = parse_request_body(r, &data)
	if rtn == 0 {
		byte_json, _ := json.Marshal(data)
		user_info, _ := simplejson.NewJson(byte_json)
		foodid, _ := user_info.Get("food_id").Int()
		count, _ := user_info.Get("count").Int()

		rtn = model.Cart_add_food(token, cartid, foodid, count)
		switch rtn {
		case 0:
			w.WriteHeader(http.StatusNoContent)
		case -1:
			w.WriteHeader(http.StatusNotFound)
			w.(http.ResponseWriter).Write([]byte(`{"code": "CART_NOT_FOUND", "message": "篮子不存在"}`))
		case -2:
			w.WriteHeader(http.StatusNotFound)
			w.(http.ResponseWriter).Write([]byte(`{"code": "FOOD_NOT_FOUND", "message": "食物不存在"}`))
		case -3:
			w.WriteHeader(http.StatusForbidden)
			w.(http.ResponseWriter).Write([]byte(`{"code": "FOOD_OUT_OF_LIMIT", "message": "篮子中食物数量超过了三个"}`))
		default:
			w.WriteHeader(http.StatusUnauthorized)
			w.(http.ResponseWriter).Write([]byte(`{"code": "NOT_AUTHORIZED_TO_ACCESS_CART", "message": "无权限访问指定的篮子"}`))
		}
	} else if rtn == -1 {
		// EOF
		w.WriteHeader(http.StatusBadRequest)
		w.(http.ResponseWriter).Write([]byte(`{"code": "EMPTY_REQUEST", "message": "请求体为空"}`))
	} else {
		w.WriteHeader(http.StatusBadRequest)
		w.(http.ResponseWriter).Write([]byte(`{"code": "MALFORMED_JSON", "message": "格式错误"}`))
	}
}

func Post_orders(w rest.ResponseWriter, r *rest.Request) {
	rtn, token := TokenChecker(r)
	if rtn < 0 {
		w.WriteHeader(http.StatusUnauthorized)
		w.(http.ResponseWriter).Write([]byte(`{"code": "INVALID_ACCESS_TOKEN", "message": "无效的令牌"}`))
		return
	}

	var data interface{}
	rtn = parse_request_body(r, &data)
	if rtn == 0 {
		byte_json, _ := json.Marshal(data)
		user_info, _ := simplejson.NewJson(byte_json)
		cart_id, _ := user_info.Get("cart_id").String()
		rtn, order_id := model.PostOrder(cart_id, token)

		if rtn == 0 {
			w.(http.ResponseWriter).Write([]byte(` {"id": ` +
				`"` + order_id + `"  }`))
		} else if rtn == -1 {
			w.WriteHeader(http.StatusNotFound)
			w.(http.ResponseWriter).Write([]byte(`{"code": "CART_NOT_FOUND", "message": "篮子不存在"}`))
		} else if rtn == -2 {
			w.WriteHeader(http.StatusUnauthorized)
			w.(http.ResponseWriter).Write([]byte(`{"code": "NOT_AUTHORIZED_TO_ACCESS_CART", "message": "无权限访问指定的篮子"}`))
		} else if rtn == -3 {
			w.WriteHeader(http.StatusForbidden)
			w.(http.ResponseWriter).Write([]byte(`{"code": "FOOD_OUT_OF_STOCK", "message": "食物库存不足"}`))
		} else {
			// rtn == -4
			w.WriteHeader(http.StatusForbidden)
			w.(http.ResponseWriter).Write([]byte(`{"code": "ORDER_OUT_OF_LIMIT", "message": "每个用户只能下一单"}`))
		}
	} else if rtn == -1 {
		// EOF
		w.WriteHeader(http.StatusBadRequest)
		w.(http.ResponseWriter).Write([]byte(`{"code": "EMPTY_REQUEST", "message": "请求体为空"}`))
	} else {
		w.WriteHeader(http.StatusBadRequest)
		w.(http.ResponseWriter).Write([]byte(`{"code": "MALFORMED_JSON", "message": "格式错误"}`))
	}
}

func get_orders(w rest.ResponseWriter, r *rest.Request) {
	// TODO: replace with middleware
	rtn, token := TokenChecker(r)
	if rtn < 0 {
		w.WriteHeader(http.StatusUnauthorized)
		w.(http.ResponseWriter).Write([]byte(`code": "INVALID_ACCESS_TOKEN", "message": "无效的令牌"}`))
		return
	}

	res, found := model.GetOrder(token)
	if !found {
		//model.L.Print("Order not found")
		w.WriteJson([]interface{}{})
		return
	}

	w.(http.ResponseWriter).Write([]byte(res))
}

func get_admin_orders(w rest.ResponseWriter, r *rest.Request) {
	// TODO: replace with middleware
	rtn, token := TokenChecker(r)
	if rtn < 0 {
		w.WriteHeader(http.StatusUnauthorized)
		w.(http.ResponseWriter).Write([]byte(`"code": "INVALID_ACCESS_TOKEN", "message": "无效的令牌"}`))
		return
	}

	res := model.AdminGetOrder(token)
	w.(http.ResponseWriter).Write([]byte(res))
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
	runtime.GOMAXPROCS(runtime.NumCPU())
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
	//api.Use(rest.DefaultDevStack...)
	router, err := rest.MakeRouter(
		rest.Get("/", Index),
		rest.Post("/login", Login),
		rest.Get("/foods", Foods),
		rest.Post("/carts", Post_carts),
		rest.Patch("/carts/:cartid", Patch_carts),
		rest.Post("/orders", Post_orders),
		rest.Get("/orders", get_orders),
		rest.Get("/admin/orders", get_admin_orders),
	)
	if err != nil {
		log.Fatal(err)
	}
	api.SetApp(router)

	log.Fatal(http.ListenAndServe(addr, api.MakeHandler()))
}
