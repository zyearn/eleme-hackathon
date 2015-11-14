#USAGE

```
EVAL "..." 4 token cart_id food_id count
```

|`KEYS[1]` |  token   |
|`KEYS[2]` |  cart_id |
|`KEYS[3]` |  food_id |
|`KEYS[4]` |  count   |

#Return Value
|`0`  |OK                             |
|`-1` |cart doesn't exist             |
|`-2` |food doesn't exist             |
|`-3` |food out of limit              |
|`-4` |not authorized to access cart  |
