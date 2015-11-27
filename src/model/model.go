package model

import (
	"../constant"
	"database/sql"
	"fmt"
	_ "github.com/go-sql-driver/mysql"
	"gopkg.in/redis.v3"
	"io/ioutil"
	"log"
	"math/rand"
	"os"
	"sort"
	"strconv"
	"sync"
	"time"
)

/** random string **/
const letterBytes = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ123456789"
const (
	letterIdxBits = 6                    // 6 bits to represent a letter index
	letterIdxMask = 1<<letterIdxBits - 1 // All 1-bits, as many as letterIdxBits
	letterIdxMax  = 63 / letterIdxBits   // # of letter indices fitting in 63 bits
)

var srcLogin = rand.NewSource(time.Now().UnixNano())
var srcCart = rand.NewSource(time.Now().UnixNano() + 1)
var srcOrder = rand.NewSource(time.Now().UnixNano() + 2)

var loginMutex sync.Mutex
var cartMutex sync.Mutex
var orderMutex sync.Mutex

func RandString(src rand.Source, n int) string {
	b := make([]byte, n)
	for i, cache, remain := n-1, src.Int63(), letterIdxMax; i >= 0; {
		if remain == 0 {
			cache, remain = src.Int63(), letterIdxMax
		}
		if idx := int(cache & letterIdxMask); idx < len(letterBytes) {
			b[i] = letterBytes[idx]
			i--
		}
		cache >>= letterIdxBits
		remain--
	}

	return string(b)
}

/** random string **/

var L = log.New(os.Stderr, "", 0)
var r = redis.NewClient(&redis.Options{
	Addr:         os.Getenv("REDIS_HOST") + ":" + os.Getenv("REDIS_PORT"),
	Password:     "",
	DB:           0,
	PoolSize:     350,
	MaxRetries:   3,
	DialTimeout:  3 * time.Second,
	ReadTimeout:  3 * time.Second,
	WriteTimeout: 3 * time.Second,
	PoolTimeout:  3 * time.Second,
	IdleTimeout:  100 * time.Second,
})

type userType struct {
	id, name, password string
}

var cache_user = make(map[string]userType) //token -> UserType
var cache_userid = make(map[string]string) //name -> id
var cache_food_price = make(map[string]int)
var cache_food_stock = make(map[string]int)
var cache_token_user = make(map[string]string)
var cache_cart_user = make(map[string]string)
var cache_food_last_update_time int

var mutex_cache_food_stock sync.Mutex
var mutex_cache_token_user sync.Mutex
var mutex_cache_cart_user sync.Mutex
var mutex_cache_food_last_update_time sync.Mutex

func atoi(str string) int {
	res, err := strconv.Atoi(str)
	if err != nil {
		L.Panic(err)
	}
	return res
}

var addFood, queryStock, placeOrder, adminQuery *redis.Script

func Load_script_from_file(filename string) *redis.Script {
	command_raw, err := ioutil.ReadFile(filename)
	if err != nil {
		L.Fatal("Failed to load script " + filename)
	}
	command := string(command_raw)
	//return r.ScriptLoad(command).Val()
	return redis.NewScript(command)
}

func PostLogin(username string, password string) (int, int, string) {
	//fmt.Println("username=" + username)
	//fmt.Println("password=" + password)

	user_id, ok := cache_userid[username]
	if !ok {
		return -1, -1, ""
	}

	password_ := cache_user[user_id].password
	if password != password_ {
		return -1, -1, ""
	}

	loginMutex.Lock()
	token := RandString(srcLogin, 8)
	loginMutex.Unlock()

	s := fmt.Sprintf("token:%s:user", token)
	r.Set(s, user_id, 0)

	mutex_cache_token_user.Lock()
	cache_token_user[token] = user_id
	mutex_cache_token_user.Unlock()

	rtn_user_id, err := strconv.Atoi(user_id)
	if err != nil {
		return -1, -1, ""
	}
	return 0, rtn_user_id, token
}

func get_token_user(token string) string {
	mutex_cache_token_user.Lock()
	id, ok := cache_token_user[token]
	mutex_cache_token_user.Unlock()

	if ok {
		return id
	} else {
		s := fmt.Sprintf("token:%s:user", token)
		user_id := r.Get(s).Val()
		if user_id != "" {
			mutex_cache_token_user.Lock()
			cache_token_user[token] = user_id
			mutex_cache_token_user.Unlock()
		}

		return user_id
	}
}

func Is_token_exist(token string) bool {
	if nid := get_token_user(token); nid == "" {
		return false
	} else {
		return true
	}
}

func get_cart_user(cartid string) string {
	mutex_cache_cart_user.Lock()
	id, ok := cache_token_user[cartid]
	mutex_cache_cart_user.Unlock()

	if ok {
		return id
	} else {
		s := fmt.Sprintf("cart:%s:user", cartid)
		user_id := r.Get(s).Val()
		if cartid != "" {
			mutex_cache_cart_user.Lock()
			cache_cart_user[cartid] = user_id
			mutex_cache_cart_user.Unlock()
		}

		return user_id
	}
}

func Create_cart(token string) string {
	cartMutex.Lock()
	cartid := RandString(srcCart, 16)
	cartMutex.Unlock()

	uid := get_token_user(token)
	r.Set(fmt.Sprintf("cart:%s:user", cartid), uid, 0)
	mutex_cache_cart_user.Lock()
	cache_cart_user[cartid] = uid
	mutex_cache_cart_user.Unlock()

	return cartid
}

func Cart_add_food(token, cartid string, foodid int, count int) int {
	foodid_s := strconv.Itoa(foodid)
	_, exist := cache_food_price[foodid_s]

	if !exist {
		return -2
	}

	cart_user := get_cart_user(cartid)
	if cart_user == "" {
		return -1
	}

	belong_user := get_token_user(token)
	if belong_user != cart_user {
		return -4
	}

	cart_items := r.HGetAll("cart:" + cartid).Val()
	sum := 0
	for i := 0; i < len(cart_items); i += 2 {
		sum += atoi(cart_items[i+1])
	}

	if sum+count > 3 {
		return -3
	}

	r.HIncrBy("cart:"+cartid, foodid_s, int64(count))

	return 0
}

func Get_foods() []map[string]interface{} {
	mutex_cache_food_last_update_time.Lock()
	_time := cache_food_last_update_time
	mutex_cache_food_last_update_time.Unlock()

	var ret []map[string]interface{}
	time_latest, e := strconv.Atoi(r.Get(constant.TIMESTAMP).Val())
	if e != nil {
		L.Fatal("err!strconv.Atoi(r.Get(constant.TIMESTAMP).Val, ", time_latest)
	} else {

		if time_latest != _time && time_latest >= 99 {
			mutex_cache_food_last_update_time.Lock()
			cache_food_last_update_time = time_latest
			mutex_cache_food_last_update_time.Unlock()

			results := r.ZRangeByScore("food:id:stock", redis.ZRangeByScore{strconv.Itoa(_time), "+inf", 0, 0}).Val()

			for i := 0; i < len(results); i += 1 {
				if results[i] == "" {
					continue
				}
				raw_number, err := strconv.ParseInt(results[i], 10, 64)
				if err != nil {
					L.Fatal("err strconv.ParseInt")
					continue
				}

				id := int(raw_number / 10000 % 100000)
				stock := int(raw_number % 10000)
				food_id := strconv.Itoa(id)

				mutex_cache_food_stock.Lock()
				cache_food_stock[food_id] = stock
				mutex_cache_food_stock.Unlock()
			}
		}
	}

	keys := []string{}
	for k, _ := range cache_food_price {
		keys = append(keys, k)
	}

	sort.Strings(keys)
	for _, v := range keys {
		k := v
		mutex_cache_food_stock.Lock()
		_stock := cache_food_stock[k]
		mutex_cache_food_stock.Unlock()

		food_id, _ := strconv.Atoi(k)
		ret = append(ret, map[string]interface{}{
			"id":    food_id,
			"price": cache_food_price[k],
			"stock": _stock,
		})
	}
	return ret
}

func PostOrder(cart_id string, token string) (int, string) {
	orderMutex.Lock()
	order_id := RandString(srcOrder, 8)
	orderMutex.Unlock()

	res, err := placeOrder.Run(r, []string{cart_id, order_id, token}, []string{}).Result()
	if err != nil {
		L.Fatal("Failed to post order, err:", err)
	}
	rtn := int(res.(int64))
	return rtn, order_id
}

func GetOrder(token string) (ret string, found bool) {
	orderid := r.Get(fmt.Sprintf("user:%s:order", get_token_user(token))).Val()
	if orderid == "" {
		found = false
		return
	}
	found = true
	//cartid := r.HGet("order:cart", orderid).Val()
	//items := r.HGetAll(fmt.Sprintf("cart:%s", cartid)).Val()
	items := r.HGetAll(fmt.Sprintf("order:%s", orderid)).Val()

	var item_str string
	total := 0
	for i := 0; i < len(items); i += 2 {
		food := items[i]
		count := items[i+1]
		f, _ := strconv.Atoi(food)
		c, _ := strconv.Atoi(count)
		price := cache_food_price[food]
		total += price * c
		if i > 0 {
			item_str += ","
		}
		item_str += `{"food_id": ` + strconv.Itoa(f) + `, "count": ` + strconv.Itoa(c) + `}`
	}
	ret = `[{` +
		`"id": ` +
		`"` + orderid + `"  ,` +
		`"items": 
		  [ ` +
		item_str +
		` ],` +
		`"total":` +
		strconv.Itoa(total) +
		`}]`
	return
}

func AdminGetOrder(token string) string {
	results := adminQuery.Run(r, []string{}, []string{}).Val().([]interface{})
	ret := "["

	for i := 0; i < len(results); i += 1 {
		if i > 0 {
			ret += ","
		}
		var result = results[i].([]interface{})
		var items = result[2].([]interface{})
		var item_str string
		var total = 0

		for j := 0; j < len(items); j += 2 {
			food, _ := strconv.Atoi(items[j].(string))
			count, _ := strconv.Atoi(items[j+1].(string))
			price := cache_food_price[items[j].(string)]
			total += price * count

			if j > 0 {
				item_str += ","
			}
			item_str += `{"food_id": ` + strconv.Itoa(food) + `, "count": ` + strconv.Itoa(count) + `}`
		}

		ret += `{` +
			`"id":` +
			`"` + result[0].(string) + `",` +
			`"user_id":` +
			result[1].(string) + `,` +
			`"items":
			[
			` + item_str +
			`],` +
			`"total":` + strconv.Itoa(total) +
			`}`
	}
	ret += `]`

	return ret
}

/** init code **/

func init_cache_and_redis(init_redis bool) {
	L.Print("Actual init begins, init_redis=", init_redis)
	addFood = Load_script_from_file("src/model/lua/add_food.lua")
	queryStock = Load_script_from_file("src/model/lua/query_stock.lua")
	placeOrder = Load_script_from_file("src/model/lua/place_order.lua")
	adminQuery = Load_script_from_file("src/model/lua/admin_query.lua")
	cache_food_last_update_time = 0
	db, dberr := sql.Open("mysql",
		os.Getenv("DB_USER")+
			":"+
			os.Getenv("DB_PASS")+
			"@tcp("+
			os.Getenv("DB_HOST")+
			":"+
			os.Getenv("DB_PORT")+
			")/"+
			os.Getenv("DB_NAME"))
	defer db.Close()
	if dberr != nil {
		L.Fatal(dberr)
	}

	now := 0
	rows, _ := db.Query("SELECT id,name,password from user")
	for rows.Next() {
		var id, name, pwd string
		rows.Scan(&id, &name, &pwd)
		cache_userid[name] = id
		cache_user[id] =
			userType{
				id:       id,
				name:     name,
				password: pwd,
			}
	}

	rows, _ = db.Query("SELECT id,stock,price from food")
	p := r.Pipeline()
	for rows.Next() {
		var id string
		var stock, price int
		rows.Scan(&id, &stock, &price)
		idInt := atoi(id)
		now += 1
		cache_food_price[id] = price
		cache_food_stock[id] = stock
		//L.Print("adding food:", id)
		if init_redis {
			p.ZAdd(constant.FOOD_ID_STOCK,
				redis.Z{
					float64(now),
					now*1000000000 + idInt*10000 + stock,
				})
			p.HSet(constant.FOOD_LAST_UPDATE_TIME, id, strconv.Itoa(now))
		}
	}

	if init_redis {
		p.Set(constant.TIMESTAMP, now, 0)
		p.Set(constant.INIT_TIME, -10000, 0)
		p.Exec()
	}

	cache_food_last_update_time = now
}

func Sync_redis_from_mysql() {
	if constant.DEBUG {
		r.Del(constant.INIT_TIME)
	}

	if r.Incr(constant.INIT_TIME).Val() == 1 {
		L.Println("Ready to init redis")
		init_cache_and_redis(true)
	} else {
		L.Println("Already been init")
		init_cache_and_redis(false)
		for atoi(r.Get(constant.INIT_TIME).Val()) >= 1 {
			time.Sleep(200 * time.Millisecond)
		}
	}
}

/** init code **/
