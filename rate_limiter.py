import time
from typing import Dict, List
from fastapi import Request

# =========================
# IN-MEMORY STORAGE
# =========================

_REQUESTS: Dict[str, List[float]] = {}
_REQUEST_COUNT = 0  # ✅ ADD THIS LINE (global request counter)

# =========================
# CLIENT IP EXTRACTION
# =========================

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    return request.client.host if request.client else "unknown"

# =========================
# CLEANUP
# =========================

def cleanup_old_requests(ttl_seconds: int = 7200):
    """
    Remove inactive IPs to prevent memory leaks.
    Default TTL: 2 hours
    """
    now = time.time()

    for key in list(_REQUESTS.keys()):
        timestamps = _REQUESTS.get(key)
        if not timestamps or max(timestamps) < now - ttl_seconds:
            _REQUESTS.pop(key, None)

# =========================
# RATE LIMIT LOGIC
# =========================

def is_rate_limited(key: str, limit: int, window_seconds: int) -> bool:
    global _REQUEST_COUNT  # ✅ REQUIRED to modify global

    now = time.time()

    timestamps = _REQUESTS.setdefault(key, [])
    timestamps[:] = [t for t in timestamps if t > now - window_seconds]

    if len(timestamps) >= limit:
        return True

    timestamps.append(now)

    # ✅ periodic cleanup every 100 requests
    _REQUEST_COUNT += 1
    if _REQUEST_COUNT % 100 == 0:
        cleanup_old_requests()

    return False
