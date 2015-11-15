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
food:stock                      {<foodid> : <stock>}
```

## Sync with MySQL

```
food:stock
```

