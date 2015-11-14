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
food:stock                     {<foodid> : <stock>}
food:price                     {<foodid> : <price>}
food_set                      { <foodid1>, <foodid2>, ... } //SET
username:<username>:userid     <userid>
username:<username>:password   <password>
```

## Sync with MySQL

```
food:stock
food:price
food_set
username:<username>:userid
username:<username>:password
```

