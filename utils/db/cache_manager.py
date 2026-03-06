from cachetools import TTLCache

users_cache = {
    "get_users": TTLCache(maxsize=1, ttl=3600),
    "_get_user_by_id": TTLCache(maxsize=100, ttl=300),
    "get_user_by_id": TTLCache(maxsize=100, ttl=300),
    "_get_user_by_nickname": TTLCache(maxsize=100, ttl=300),
    "get_user_by_nickname": TTLCache(maxsize=100, ttl=300)
}

def clear_cache():
    for _, cache in users_cache.items():
        cache.clear()