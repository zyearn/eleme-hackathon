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
	"strconv"
	"time"
)

/** random string **/
const letterBytes = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
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

var l = log.New(os.Stderr, "", 0)
var r = redis.NewClient(&redis.Options{
	Addr:     os.Getenv("REDIS_HOST") + ":" + os.Getenv("REDIS_PORT"),
	Password: "",
	DB:       0,
})

type userType struct {
	id, name, password string
}

var cache_food_last_update_time = make(map[int]int)
var cache_user = make(map[string]userType) //token -> UserType
var cache_userid = make(map[string]string) //name -> id
var cache_food_price = make(map[string]int)
var cache_food_stock = make(map[string]int)
var cache_token_user = make(map[string]string)

func atoi(str string) int {
	res, err := strconv.Atoi(str)
	if err != nil {
		l.Panic(err)
	}
	return res
}

func Load_script_from_file(filename string) string {
	command_raw, err := ioutil.ReadFile(filename)
	if err != nil {
		l.Fatal("Failed to load script " + filename)
	}
	command := string(command_raw)
	return r.ScriptLoad(command).Val()
}

func PostLogin(username string, password string) (int, string) {
	fmt.Println("username=" + username)
	fmt.Println("password=" + password)

	user_id := cache_userid[username]
	if user_id == "" {
		return -1, ""
	}

	password_ := cache_user[user_id].password
	if password != password_ {
		return -1, ""
	}

	token := RandString(8)
	s := fmt.Sprintf("token:%s:user", token)
	r.Set(s, user_id, 0)
	cache_token_user[token] = user_id
	return 0, user_id
}

var addFood, queryStock, placeOrder string

func Sync_redis_from_mysql() {
	/*
		if r.Incr(constant.INIT_TIME).Val() == 1 {
			l.Println("Ready to init redis")
		} else {
			l.Println("Already been init")
			for atoi(r.Get(constant.INIT_TIME).Val()) >= 1 {
				time.Sleep(200 * time.Millisecond)
			}
			return
		}
	*/
	addFood = Load_script_from_file("src/model/lua/add_food.lua")
	queryStock = Load_script_from_file("src/model/lua/query_stock.lua")
	placeOrder = Load_script_from_file("src/model/lua/place_order.lua")
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
		l.Fatal(dberr)
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
		p.ZAdd(constant.FOOD_STOCK_KIND,
			redis.Z{
				float64(now),
				now*constant.TIME_BASE + idInt,
			})
		p.ZAdd(constant.FOOD_STOCK_COUNT,
			redis.Z{
				float64(now),
				now*constant.TIME_BASE + stock,
			})
		p.HSet(constant.FOOD_LAST_UPDATE_TIME, id, strconv.Itoa(now))
	}
	p.Set(constant.TIMESTAMP, now, 0)
	p.Exec()
	//r.Set(constant.INIT_TIME, -10000)
}
