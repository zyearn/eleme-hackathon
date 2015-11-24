package main

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"io/ioutil"
	"math/rand"
	"net/http"
	"net/url"
	"os"
	"runtime"
	"sort"
	"strings"
	"time"

	"github.com/garyburd/redigo/redis"
	_ "github.com/go-sql-driver/mysql"
)

//----------------------------------
// Stress Settings
//----------------------------------
const (
	MAX_COCURRENCY   = 10 * 1024
	REDIS_LOCAL_ADDR = "127.0.0.1:6379"
)

//----------------------------------
// Stress Abstracts
//----------------------------------
type Worker struct {
	r   *Reporter
	ctx struct {
		hosts []string
		port  int
	}
}

type Context struct {
	c      *http.Client
	w      *Worker
	user   User
	cartId string
}

type Reporter struct {
	orderMade       chan bool
	orderCost       chan time.Duration
	requestSent     chan bool
	userCurr        chan User
	numOrders       int
	cocurrency      int
	nOrderOk        int
	nOrderErr       int
	nOrderTotal     int
	nOrderPerSec    []int
	orderCosts      []time.Duration
	nRequestOk      int
	nRequestErr     int
	nRequestTotal   int
	nRequestPerSec  []int
	timeStampPerSec []int
	startAt         time.Time
	elapsed         time.Duration
}

//----------------------------------
// Entity Abstracts
//----------------------------------
type User struct {
	Id          int
	UserName    string
	PassWord    string
	AccessToken string
}

type Food struct {
	Id    int `json:"id"`
	Price int `json:"price"`
	Stock int `json:"stock"`
}

//----------------------------------
// Request JSON Bindings
//----------------------------------
type RequestLogin struct {
	UserName string `json:"username"`
	PassWord string `json:"password"`
}

type RequestCartAddFood struct {
	FoodId int `json:"food_id"`
	Count  int `json:"count"`
}

type RequestMakeOrder struct {
	CartId string `json:"cart_id"`
}

//----------------------------------
// Response JSON Bindings
//----------------------------------
type ResponseLogin struct {
	UserId      int    `json:"user_id"`
	UserName    string `json:"username"`
	AccessToken string `json:"access_token"`
}

type ResponseGetFoods []Food

type ResponseCreateCart struct {
	CartId string `json:"cart_id"`
}

type ResponseMakeOrder struct {
	Id   string `json:"id"`
	Item []struct {
		FoodId int
		Count  int
	} `json:"items"`
	Total int `json:"total"`
}

//----------------------------------
// Global Variables
//----------------------------------
var (
	users           = make([]User, 0)    // users
	foods           = make(map[int]Food) // map[food.Id]food
	isDebugMode     = false
	isReportToRedis = false
)

//----------------------------------
// Data Initialization
//----------------------------------
// Load all data.
func LoadData() {
	dbHost := os.Getenv("DB_HOST")
	dbPort := os.Getenv("DB_PORT")
	dbName := os.Getenv("DB_NAME")
	dbUser := os.Getenv("DB_USER")
	dbPass := os.Getenv("DB_PASS")

	if dbHost == "" {
		dbHost = "localhost"
	}
	if dbPort == "" {
		dbPort = "3306"
	}
	if dbName == "" {
		dbName = "eleme"
	}
	if dbUser == "" {
		dbUser = "root"
	}
	if dbPass == "" {
		dbPass = "toor"
	}

	fmt.Printf("Connect to mysql..")
	dbDsn := fmt.Sprintf("%s:%s@tcp(%s:%s)/%s", dbUser, dbPass, dbHost, dbPort, dbName)
	db, err := sql.Open("mysql", dbDsn)
	if err != nil {
		panic(err)
	}
	defer db.Close()
	fmt.Printf("OK\n")
	fmt.Printf("Ping to mysql..")
	err = db.Ping()
	if err != nil {
		panic(err)
	}
	fmt.Printf("OK\n")
	fmt.Printf("Load users from mysql..")
	LoadUsers(db)
	fmt.Printf("OK\n")
	fmt.Printf("Load foods from mysql..")
	LoadFoods(db)
	fmt.Printf("OK\n")
}

// Load users from mysql
func LoadUsers(db *sql.DB) {
	var user User
	rows, err := db.Query("SELECT `id`, `name`, `password` from user")
	if err != nil {
		panic(err)
	}
	defer rows.Close()
	for rows.Next() {
		err = rows.Scan(&user.Id, &user.UserName, &user.PassWord)
		if err != nil {
			panic(err)
		}
		users = append(users, user)
	}
}

// Load foods from mysql
func LoadFoods(db *sql.DB) {
	var food Food
	rows, err := db.Query("SELECT `id`, `stock`, `price` from food")
	if err != nil {
		panic(err)
	}
	defer rows.Close()
	for rows.Next() {
		err = rows.Scan(&food.Id, &food.Stock, &food.Price)
		if err != nil {
			panic(err)
		}
		foods[food.Id] = food
	}
}

//----------------------------------
// Request Utils
//----------------------------------
// Build url with path and parameters.
func (w *Worker) Url(path string, params url.Values) string {
	// random choice one host for load balance
	i := rand.Intn(len(w.ctx.hosts))
	host := w.ctx.hosts[i]
	s := fmt.Sprintf("http://%s:%d%s", host, w.ctx.port, path)
	if params == nil {
		return s
	}
	p := params.Encode()
	return fmt.Sprintf("%s?%s", s, p)
}

// Get json from uri.
func (w *Worker) Get(c *http.Client, url string, bind interface{}) (int, error) {
	r, err := c.Get(url)
	if err != nil {
		if r != nil {
			ioutil.ReadAll(r.Body)
			r.Body.Close()
		}
		return 0, err
	}
	defer r.Body.Close()
	err = json.NewDecoder(r.Body).Decode(bind)
	if bind == nil {
		return r.StatusCode, nil
	}
	return r.StatusCode, err
}

// Post json to uri and get json response.
func (w *Worker) Post(c *http.Client, url string, data interface{}, bind interface{}) (int, error) {
	var body io.Reader
	if data != nil {
		bs, err := json.Marshal(data)
		if err != nil {
			return 0, err
		}
		body = bytes.NewReader(bs)
	}
	r, err := c.Post(url, "application/json", body)
	if err != nil {
		if r != nil {
			ioutil.ReadAll(r.Body)
			r.Body.Close()
		}
		return 0, err
	}
	defer r.Body.Close()
	err = json.NewDecoder(r.Body).Decode(bind)
	if bind == nil {
		return r.StatusCode, nil
	}
	return r.StatusCode, err
}

// Patch url with json.
func (w *Worker) Patch(c *http.Client, url string, data interface{}, bind interface{}) (int, error) {
	bs, err := json.Marshal(data)
	if err != nil {
		return 0, err
	}
	req, err := http.NewRequest("PATCH", url, bytes.NewReader(bs))
	if err != nil {
		return 0, err
	}
	req.Header.Set("Content-Type", "application/json")
	res, err := c.Do(req)
	if err != nil {
		if res != nil {
			ioutil.ReadAll(res.Body)
			res.Body.Close()
		}
		return 0, err
	}
	defer res.Body.Close()
	err = json.NewDecoder(res.Body).Decode(bind)
	if res.StatusCode == http.StatusNoContent || bind == nil {
		return res.StatusCode, nil
	}
	return res.StatusCode, err
}

//----------------------------------
//  Order Handle Utils
//----------------------------------
// Random choice a food. Dont TUCAO this function,
// it works and best O(1).
func GetRandFood() Food {
	for {
		idx := rand.Intn(len(foods))
		food, ok := foods[idx+1]
		if ok {
			return food
		}
	}
}

//----------------------------------
//  Work Job Context
//----------------------------------
func (ctx *Context) UrlWithToken(path string) string {
	user := ctx.user
	params := url.Values{}
	params.Add("access_token", user.AccessToken)
	return ctx.w.Url(path, params)
}

func (ctx *Context) Login() bool {
	user := ctx.user
	data := &RequestLogin{user.UserName, user.PassWord}
	body := &ResponseLogin{}
	url := ctx.w.Url("/login", nil)
	statusCode, err := ctx.w.Post(ctx.c, url, data, body)
	if err != nil {
		if isDebugMode {
			fmt.Printf("Request login error: %v\n", err)
		}
		ctx.w.r.requestSent <- false
		return false
	}
	if statusCode == http.StatusOK {
		ctx.user.AccessToken = body.AccessToken
		ctx.w.r.requestSent <- true
		return true
	}
	ctx.w.r.requestSent <- false
	return false
}

func (ctx *Context) GetFoods() bool {
	// body := &ResponseGetFoods{}
	url := ctx.UrlWithToken("/foods")
	statusCode, err := ctx.w.Get(ctx.c, url, nil)
	if err != nil {
		if isDebugMode {
			fmt.Printf("Request get foods error: %v\n", err)
		}
		ctx.w.r.requestSent <- false
		return false
	}
	if statusCode == http.StatusOK {
		ctx.w.r.requestSent <- true
		return true
	}
	ctx.w.r.requestSent <- false
	return false
}

func (ctx *Context) CreateCart() bool {
	body := &ResponseCreateCart{}
	url := ctx.UrlWithToken("/carts")
	statusCode, err := ctx.w.Post(ctx.c, url, nil, body)
	if err != nil {
		if isDebugMode {
			fmt.Printf("Request create carts error: %v\n", err)
		}
		ctx.w.r.requestSent <- false
		return false
	}
	if statusCode == http.StatusOK {
		ctx.cartId = body.CartId
		ctx.w.r.requestSent <- true
		return true
	}
	ctx.w.r.requestSent <- false
	return false
}

func (ctx *Context) CartAddFood() bool {
	path := fmt.Sprintf("/carts/%s", ctx.cartId)
	url := ctx.UrlWithToken(path)
	food := GetRandFood()
	data := &RequestCartAddFood{food.Id, 1}
	statusCode, err := ctx.w.Patch(ctx.c, url, data, nil)
	if err != nil {
		if isDebugMode {
			fmt.Printf("Request error cart add food error: %v\n", err)
		}
		ctx.w.r.requestSent <- false
		return false
	}
	if statusCode == http.StatusNoContent {
		ctx.w.r.requestSent <- true
		return true
	}
	ctx.w.r.requestSent <- false
	return false
}

func (ctx *Context) MakeOrder() bool {
	if !ctx.Login() || !ctx.GetFoods() || !ctx.CreateCart() {
		return false
	}
	count := rand.Intn(3) + 1
	for i := 0; i < count; i++ {
		if !ctx.CartAddFood() {
			return false
		}
	}
	data := &RequestMakeOrder{ctx.cartId}
	body := &ResponseMakeOrder{}
	url := ctx.UrlWithToken("/orders")
	statusCode, err := ctx.w.Post(ctx.c, url, data, body)
	if err != nil {
		if isDebugMode {
			fmt.Printf("Request make order error: %v\n", err)
		}
		ctx.w.r.requestSent <- false
		return false
	}
	if statusCode == http.StatusOK {
		ctx.w.r.requestSent <- true
		return true
	}
	ctx.w.r.requestSent <- false
	return false
}

//----------------------------------
// Worker
//----------------------------------
func NewWorker(hosts []string, port int, r *Reporter) *Worker {
	w := &Worker{}
	w.r = r
	w.ctx.hosts = hosts
	w.ctx.port = port
	return w
}
func (w *Worker) Work() {
	ctx := &Context{}
	ctx.w = w
	t := &http.Transport{}
	ctx.c = &http.Client{
		Timeout:   3 * time.Second,
		Transport: t,
	}
	for {
		t.CloseIdleConnections()
		startAt := time.Now()
		ctx.user = <-w.r.userCurr
		w.r.orderMade <- ctx.MakeOrder()
		w.r.orderCost <- time.Since(startAt)
	}
}

//----------------------------------
// Statstics Reporter
//----------------------------------
// Create reporter
func NewReporter(numOrders int, cocurrency int) *Reporter {
	return &Reporter{
		make(chan bool, cocurrency),
		make(chan time.Duration, cocurrency),
		make(chan bool, cocurrency),
		make(chan User, cocurrency),
		numOrders,
		cocurrency,
		0,
		0,
		0,
		make([]int, 0),
		make([]time.Duration, 0),
		0,
		0,
		0,
		make([]int, 0),
		make([]int, 0),
		time.Now(),
		0,
	}
}

// Start reporter
func (r *Reporter) Start() {
	r.startAt = time.Now()
	go func() {
		t := time.NewTicker(1 * time.Second)
		for {
			nOrderOk := r.nOrderOk
			nRequestOk := r.nRequestOk
			<-t.C
			nOrderPerSec := r.nOrderOk - nOrderOk
			r.nOrderPerSec = append(r.nOrderPerSec, nOrderPerSec)
			nRequestPerSec := r.nRequestOk - nRequestOk
			r.nRequestPerSec = append(r.nRequestPerSec, nRequestPerSec)
			r.timeStampPerSec = append(r.timeStampPerSec, time.Now().Second())
			fmt.Printf("Finished orders: %d\n", nOrderPerSec)
		}
	}()
	go func() {
		for {
			orderMade := <-r.orderMade
			orderCost := <-r.orderCost
			if orderMade {
				r.nOrderOk = r.nOrderOk + 1
				r.orderCosts = append(r.orderCosts, orderCost)
			} else {
				r.nOrderErr = r.nOrderErr + 1
			}
			r.nOrderTotal = r.nOrderTotal + 1
			if r.nOrderTotal >= r.numOrders {
				r.Stop()
			}
		}
	}()
	go func() {
		for {
			requestSent := <-r.requestSent
			if requestSent {
				r.nRequestOk = r.nRequestOk + 1
			} else {
				r.nRequestErr = r.nRequestErr + 1
			}
			r.nRequestTotal = r.nRequestTotal + 1
		}
	}()
	for i := 0; i < len(users); i++ {
		r.userCurr <- users[i]
	}
	timeout := time.After(3 * time.Second)
	for r.nOrderTotal < r.numOrders {
		select {
		case <-timeout:
			r.Stop()
		}
	}
	r.Stop()
}

// Stop the reporter and exit full process.
func (r *Reporter) Stop() {
	r.elapsed = time.Since(r.startAt)
	r.Report()
	os.Exit(0)
}

// Report stats to console and redis.
func (r *Reporter) Report() {
	//---------------------------------------------------
	// Report to console
	//---------------------------------------------------
	sort.Ints(r.nOrderPerSec)
	sort.Ints(r.nRequestPerSec)
	nOrderPerSecMax := MeanOfMaxFive(r.nOrderPerSec)
	nOrderPerSecMin := MeanOfMinFive(r.nOrderPerSec)
	nOrderPerSecMean := Mean(r.nOrderPerSec)
	nRequestPerSecMax := MeanOfMaxFive(r.nRequestPerSec)
	nRequestPerSecMin := MeanOfMinFive(r.nRequestPerSec)
	nRequestPerSecMean := Mean(r.nRequestPerSec)
	sort.Ints(r.nRequestPerSec)
	orderCostSeconds := []float64{}
	for i := 0; i < len(r.orderCosts); i++ {
		orderCostSeconds = append(orderCostSeconds, r.orderCosts[i].Seconds())
	}
	sort.Float64s(orderCostSeconds)
	msTakenTotal := int(r.elapsed.Nanoseconds() / 1000000.0)
	msPerOrder := MeanFloat64(orderCostSeconds) * 1000.0
	msPerRequest := SumFloat64(orderCostSeconds) * 1000.0 / float64(r.nRequestOk)
	//---------------------------------------------------
	// Report to console
	//---------------------------------------------------
	fmt.Print("\nStats\n")
	fmt.Printf("Concurrency level:         %d\n", r.cocurrency)
	fmt.Printf("Time taken for tests:      %dms\n", msTakenTotal)
	fmt.Printf("Complete requests:         %d\n", r.nRequestOk)
	fmt.Printf("Failed requests:           %d\n", r.nRequestErr)
	fmt.Printf("Complete orders:           %d\n", r.nOrderOk)
	fmt.Printf("Failed orders:             %d\n", r.nOrderErr)
	fmt.Printf("Time per request:          %.2fms\n", msPerRequest)
	fmt.Printf("Time per order:            %.2fms\n", msPerOrder)
	fmt.Printf("Request per second:        %d (max)  %d (min)  %d(mean)\n", nRequestPerSecMax, nRequestPerSecMin, nRequestPerSecMean)
	fmt.Printf("Order per second:          %d (max)  %d (min)  %d (mean)\n\n", nOrderPerSecMax, nOrderPerSecMin, nOrderPerSecMean)
	fmt.Printf("Percentage of orders made within a certain time (ms)\n")
	if len(orderCostSeconds) == 0 {
		return
	}
	percentages := []int{50, 75, 80, 90, 95, 98, 100}
	for _, percentage := range percentages {
		idx := int(float64(percentage*len(orderCostSeconds)) / float64(100.0))
		if idx > 0 {
			idx = idx - 1
		} else {
			idx = 0
		}
		orderCostSecond := orderCostSeconds[idx]
		fmt.Printf("%d%%\t%d\n", percentage, int(orderCostSecond*1000.0))
	}
	//---------------------------------------------------
	// Report to redis
	//---------------------------------------------------
	if !isReportToRedis {
		return
	}
	conn, err := redis.Dial("tcp", REDIS_LOCAL_ADDR)
	defer conn.Close()
	if err != nil {
		panic(err)
	}
	conn.Do("SET", "stress_test:make_order:success", r.nOrderOk)
	conn.Do("SET", "stress_test:make_order:failure", r.nOrderErr)
	conn.Do("SET", "stress_test:make_order:req_success", r.nRequestErr)
	conn.Do("SET", "stress_test:make_order:req_failure", r.nRequestErr)
	conn.Do("SET", "stress_test:make_order:max_order_sec", nOrderPerSecMax)
	conn.Do("SET", "stress_test:make_order:min_order_sec", nOrderPerSecMin)
	conn.Do("SET", "stress_test:make_order:mean_order_sec", nOrderPerSecMean)
	conn.Do("SET", "stress_test:make_order:max_req_sec", nRequestPerSecMax)
	conn.Do("SET", "stress_test:make_order:min_req_sec", nRequestPerSecMin)
	conn.Do("SET", "stress_test:make_order:mean_req_sec", nRequestPerSecMean)
	conn.Do("SET", "stress_test:make_order:time_per_order", msPerOrder)
	conn.Do("SET", "stress_test:make_order:time_per_req", msPerRequest)
	for i := 0; i < len(r.timeStampPerSec); i++ {
		conn.Do("HSET", "stress_test:make_order:order_sec", r.timeStampPerSec[i], r.nOrderPerSec[i])
		conn.Do("HSET", "stress_test:make_order:req_sec", r.timeStampPerSec[i], r.nRequestPerSec[i])
	}
}

//----------------------------------
// Math util functions
//----------------------------------
func MeanOfMaxFive(sortedArr []int) int {
	if len(sortedArr) == 0 {
		return 0
	}
	if len(sortedArr) == 1 {
		return sortedArr[0]
	}
	if len(sortedArr) == 2 {
		return sortedArr[1]
    }
	sortedArr = sortedArr[1 : len(sortedArr)-1]
	if len(sortedArr) > 5 {
		return Mean(sortedArr[len(sortedArr)-5:])
	}
	return sortedArr[len(sortedArr)-1]
}

func MeanOfMinFive(sortedArr []int) int {
	if len(sortedArr) == 0 {
		return 0
	}
	if len(sortedArr) == 1 {
		return sortedArr[0]
	}
	if len(sortedArr) == 2 {
		return sortedArr[0]
    }
	sortedArr = sortedArr[1 : len(sortedArr)-1]
	if len(sortedArr) > 5 {
		return Mean(sortedArr[0:5])
	}
	return sortedArr[0]
}

func Mean(arr []int) int {
	if len(arr) == 0 {
		return 0
	}
	sum := 0
	for i := 0; i < len(arr); i++ {
		sum = sum + arr[i]
	}
	return int(float64(sum) / float64(len(arr)))
}

func MeanFloat64(arr []float64) float64 {
	return SumFloat64(arr) / float64(len(arr))
}

func SumFloat64(arr []float64) float64 {
	if len(arr) == 0 {
		return 0
	}
	sum := 0.0
	for i := 0; i < len(arr); i++ {
		sum = sum + arr[i]
	}
	return sum
}

//----------------------------------
// Main
//----------------------------------
func main() {
	runtime.GOMAXPROCS(runtime.NumCPU())
	//----------------------------------
	// Arguments parsing and validation
	//----------------------------------
	hosts := flag.String("h", "localhost", "server hosts, split by comma")
	port := flag.Int("p", 8080, "server port")
	cocurrency := flag.Int("c", 1000, "request cocurrency")
	numOrders := flag.Int("n", 1000, "number of orders to perform")
	debug := flag.Bool("d", false, "debug mode")
	reportRedis := flag.Bool("r", true, "report to local redis")
	flag.Parse()
	if flag.NFlag() == 0 {
		flag.PrintDefaults()
		os.Exit(1)
	}
	if *debug {
		isDebugMode = true
	}
	if *reportRedis {
		isReportToRedis = true
	}
	//----------------------------------
	// Validate cocurrency
	//----------------------------------
	if *cocurrency > MAX_COCURRENCY {
		fmt.Printf("Exceed max cocurrency (is %d)", MAX_COCURRENCY)
		os.Exit(1)
	}
	//----------------------------------
	// Load users/foods and work
	//----------------------------------
	LoadData()
	reporter := NewReporter(*numOrders, *cocurrency)
	for i := 0; i < *cocurrency; i++ {
		go func() {
			w := NewWorker(strings.Split(*hosts, ","), *port, reporter)
			w.Work()
		}()
	}
	// start reporter
	reporter.Start()
}
