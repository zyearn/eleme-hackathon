package model

import (
	//"../constant"
	"bytes"
	"database/sql"
	"fmt"
	_ "github.com/go-sql-driver/mysql"
	"gopkg.in/redis.v3"
	"io/ioutil"
	"log"
	"math/rand"
	"os"
	"strconv"
	"strings"
	"time"
)

/** random string **/
const letterBytes = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ123456789"
const (
	letterIdxBits = 6                    // 6 bits to represent a letter index
	letterIdxMask = 1<<letterIdxBits - 1 // All 1-bits, as many as letterIdxBits
	letterIdxMax  = 63 / letterIdxBits   // # of letter indices fitting in 63 bits
)

var src = rand.NewSource(time.Now().UnixNano())

func RandString(n int) string {
	b := make([]byte, n)
	// A src.Int63() generates 63 random bits, enough for letterIdxMax characters!
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
	Addr:     os.Getenv("REDIS_HOST") + ":" + os.Getenv("REDIS_PORT"),
	Password: "",
	DB:       0,
})
var db, dberr = sql.Open("mysql",
	os.Getenv("DB_USER")+
		":"+
		os.Getenv("DB_PASS")+
		"@tcp("+
		os.Getenv("DB_HOST")+
		":"+
		os.Getenv("DB_PORT")+
		")/"+
		os.Getenv("DB_NAME"))

type userType struct {
	id, name, password string
}

var cache_userid_to_info = make(map[string]userType) //token -> UserType
var cache_username_to_id = make(map[string]string)   //name -> id
var cache_food_price = make(map[string]int)
var cache_food_stock = make(map[string]int)
var cache_token_user = make(map[string]string)
var cache_food_last_update_time int

func atoi(str string) int {
	res, err := strconv.Atoi(str)
	if err != nil {
		L.Panic(err)
	}
	return res
}

var addFood, queryStock, placeOrder *redis.Script

func Load_script_from_file(filename string) *redis.Script {
	command_raw, err := ioutil.ReadFile(filename)
	if err != nil {
		L.Fatal("Failed to load script " + filename)
	}
	command := string(command_raw)
	//return r.ScriptLoad(command).Val()
	return redis.NewScript(command)
}

func PostLogin(username string, password string) (int, string, string) {
	//fmt.Println("username=" + username)
	//fmt.Println("password=" + password)

	user_id, ok := cache_username_to_id[username]
	if !ok {
		return -1, "", ""
	}

	password_ := cache_userid_to_info[user_id].password
	if password != password_ {
		return -1, "", ""
	}

	token := RandString(8)
	//fmt.Println("token = " + token)
	s := fmt.Sprintf("token:%s:user", token)
	r.Set(s, user_id, 0)
	cache_token_user[token] = user_id
	return 0, user_id, token
}

func get_token_user(token string) string {
	if id, ok := cache_token_user[token]; ok {
		return id
	} else {
		s := fmt.Sprintf("token:%s:user", token)
		user_id := r.Get(s).Val()
		if user_id != "" {
			cache_token_user[token] = user_id
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

func Create_cart(token string) string {
	cartid := RandString(32)

	r.Set(fmt.Sprintf("cart:%s:user", cartid), get_token_user(token), 0)
	//TODO: cache
	return cartid
}

func Cart_add_food(token, cartid string, foodid int, count int) int {
	foodid_s := strconv.Itoa(foodid)
	num, exist := cache_food_price[foodid_s]
	if !exist {
		L.Print(foodid, " has ", num)
		return -2
	}
	//TODO: cache
	s := fmt.Sprintf("cart:%s:user", cartid)
	cart_user := r.Get(s).Val()
	if cart_user == "" {
		return -1
	}

	token_user := get_token_user(token)
	if token_user != cart_user {
		return -4
	}

	s = fmt.Sprintf("select sum(count) from cartfood where cartid = '%s' group by cartid", cartid)
	fmt.Println("s = ", s)

	rows, err := db.Query(s)
	defer rows.Close()
	if err != nil {
		fmt.Println("select sum(count) from cartfood where cartid = %s group by cartid sql error: ", err)
	}
	var curSum = 0
	if rows.Next() {
		rows.Scan(&curSum)
	}

	if curSum+count > 3 {
		return -3
	}

	s = fmt.Sprintf("insert into cartfood(cartid, foodid, count) values('%s', %d, %d) on duplicate key update count=count+%d;",
		cartid, foodid, count, count)
	r, err := db.Query(s)
	defer r.Close()
	if err != nil {
		fmt.Println("insert into cartfood(cartid, foodid, count) values(%s, %s, %s) on duplicate key update count=count+%s; sql error: ", err)
	}

	return 0
}

func Get_foods() []map[string]interface{} {
	rows, dberr := db.Query("SELECT id, stock from food")
	defer rows.Close()

	if dberr != nil {
		fmt.Println("DB error,", dberr)
	}

	var ret []map[string]interface{}
	var id string
	var stock int

	for rows.Next() {
		rows.Scan(&id, &stock)
		food_id, _ := strconv.Atoi(id)

		ret = append(ret, map[string]interface{}{
			"id":    food_id,
			"price": cache_food_price[id],
			"stock": stock,
		})
	}
	return ret
}

func PostOrder(cart_id string, token string) (int, string) {
	order_id := RandString(16)

	//TODO: cache
	s := fmt.Sprintf("cart:%s:user", cart_id)
	cart_user := r.Get(s).Val()
	if cart_user == "" {
		fmt.Println("ready to return -1")
		return -1, ""
	}

	token_user := get_token_user(token)
	if token_user != cart_user {
		fmt.Println("ready to return -2")
		return -2, ""
	}

	s = fmt.Sprintf("select id from userorder where userid=%s", token_user)
	userorder, err := db.Query(s)
	defer userorder.Close()
	if err != nil {
		fmt.Println("order 1 db err:", err)
	}

	if userorder.Next() {
		fmt.Println("ready to return -4")
		return -4, ""
	}

	s = fmt.Sprintf("select foodid,count,stock from cartfood inner join food on cartfood.foodid=food.id where cartfood.cartid = '%s'", cart_id)
	foods_in_cart, err := db.Query(s)
	defer foods_in_cart.Close()
	if err != nil {
		fmt.Println("order 2 db err:", err)
	}

	var food_id, count, stock int
	var to_update = make(map[int]int)
	for foods_in_cart.Next() {
		foods_in_cart.Scan(&food_id, &count, &stock)
		fmt.Println("count=", count, " stock=", stock)
		if count > stock {
			fmt.Println("ready to return -3, count=", count, " stock=", stock)
			return -3, ""
		}
		to_update[food_id] = stock - count
		fmt.Println("ready to_update,", food_id, to_update[food_id])
	}

	// update stock
	var buffer bytes.Buffer
	var tail bytes.Buffer
	buffer.WriteString("update food set stock = case ")
	for k, v := range to_update {
		buffer.WriteString(fmt.Sprintf("when id=%d then %d ", k, v))
		tail.WriteString(fmt.Sprintf("%d,", k))
	}
	buffer.WriteString("end where id in(")
	ts := tail.String()
	ts = strings.TrimRight(ts, ",")

	qs := buffer.String() + ts + ")"
	fmt.Println("in place order, qs = ", qs)

	update, err := db.Query(qs)
	defer update.Close()

	if err != nil {
		fmt.Println("order 3 db err:", err)
	}

	// update order
	qs = fmt.Sprintf("insert into userorder(userid, cartid, orderid) values('%s', '%s', '%s')", token_user, cart_id, order_id)

	insert, err := db.Query(qs)
	defer insert.Close()

	if err != nil {
		fmt.Println("order 4 db err:", err)
	}

	fmt.Println("ready to return 0")
	return 0, order_id
}

func GetOrder(token string) (ret map[string]interface{}, found bool) {
	userid := get_token_user(token)
	uid, _ := strconv.Atoi(userid)

	qs := fmt.Sprintf("select userid, foodid, count from cartfood inner join userorder on cartfood.cartid = userorder.cartid where userid=%d", uid)
	fmt.Println("in getOrder! qs=", qs)
	orders, err := db.Query(qs)
	defer orders.Close()

	if err != nil {
		fmt.Println("get order 1 db err:", err)
	}

	found = false
	var item_arr []map[string]int
	var orderid string
	var foodid, count int
	total := 0

	for orders.Next() {
		found = true
		orders.Scan(&orderid, &foodid, &count)
		fmt.Println("!!!!read from sql, order,food,count=", orderid, foodid, count)
		price := cache_food_price[strconv.Itoa(foodid)]
		total = total + price*count
		fmt.Println("total=", total, "price=", price, "count=", count, "price*count=", price, "foodid=", strconv.Itoa(foodid))
		item_arr = append(item_arr, map[string]int{"food_id": foodid, "count": count})
	}

	if !found {
		return
	}

	ret = map[string]interface{}{
		"userid":  uid,
		"orderid": orderid,
		"items":   item_arr,
		"total":   total,
	}

	return
}

/** init code **/

func Init_cache() {
	if dberr != nil {
		L.Fatal(dberr)
	}

	db.SetMaxOpenConns(1500)
	db.SetMaxIdleConns(1000)

	rows, _ := db.Query("SELECT id, name, password from user")
	defer rows.Close()
	var id, name, pwd string

	for rows.Next() {
		rows.Scan(&id, &name, &pwd)
		cache_username_to_id[name] = id
		cache_userid_to_info[id] =
			userType{
				id:       id,
				name:     name,
				password: pwd,
			}
	}

	foods, _ := db.Query("SELECT id,stock,price from food")
	defer foods.Close()

	var stock, price int
	for foods.Next() {
		foods.Scan(&id, &stock, &price)
		cache_food_price[id] = price
		L.Print("adding food:", id, "price = ", price)
	}
}

/** init code **/
