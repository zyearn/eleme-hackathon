# Model Design

## Redis Key / Value

```
        KEY                         VALUE
token:<tokenid>:user           <userid>
user:<userid>:order            <orderid>
cart:<cartid>:user             <userid>
cart:<cartid>                  { <foodid>: <cnt> }
order:<orderid>:user           <userid>
order:<orderid>                { <foodid>: <cnt> }
food:<foodid>:count            <count>
food:<foodid>:price            <price>
food_list                      [ <foodid1>, <foodid2>, ... ]
username:<username>:userid     <userid>
username:<username>:password   <password>
```

## Sync with MySQL

```
food:<foodid>:count
food:<foodid>:price
food_list
username:<username>:userid
username:<username>:password
```

