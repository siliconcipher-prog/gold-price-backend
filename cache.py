import time
from typing import Any, Dict, Tuple

# key -> (expiry_timestamp, value)
_CACHE: Dict[str, Tuple[float, Any]] = {}


def get_cache(key: str):
    item = _CACHE.get(key)
    if not item:
        return None

    expires_at, value = item
    if time.time() > expires_at:
        _CACHE.pop(key, None)
        return None

    return value


def set_cache(key: str, value: Any, ttl_seconds: int):
    _CACHE[key] = (time.time() + ttl_seconds, value)


def clear_cache(prefix: str | None = None):
    if not prefix:
        _CACHE.clear()
        return

    for k in list(_CACHE.keys()):
        if k.startswith(prefix):
            _CACHE.pop(k, None)
