# Model Design

## Redis Key / Value

```
        KEY                         VALUE
token:<tokenid>:user            <userid>
user:<userid>:order             <orderid>
cart:<cartid>:user              <userid>
cart:<cartid>                   {<foodid>: <cnt> }
order:<orderid>:user            <userid>
order:cart                      {<order>: <cart>}
food:stock                      ordered set
food:last_update_time           <last_update_time>
```

## Sync with MySQL

```
food:stock
```

