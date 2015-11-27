# Model Design

## Redis Key / Value

```
        KEY                         VALUE
token:<tokenid>:user            <userid>
user:<userid>:order             <orderid>
cart:<cartid>:user              <userid>
cart:<cartid>                   {<foodid>: <cnt> }
//order:<orderid>:user            <userid>
order:user                      {<orderid>: <userid>}

order:<orderid>                 {<foodid>: <cnt> }

food:id:stock                   ordered set: <updated-time> -> <foodcount>
food:last_update_time           <last_update_time>
timestamp                       current time
```

## Sync with MySQL

```
food:stock
```

