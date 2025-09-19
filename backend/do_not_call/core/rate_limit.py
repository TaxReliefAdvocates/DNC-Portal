from __future__ import annotations

import time
from typing import Callable, Optional
from fastapi import HTTPException, Request, status, Depends
from .auth import get_principal, Principal
from ..config import settings

_memory_counts: dict[str, tuple[int, float]] = {}

_redis = None
try:
    import redis  # type: ignore
    if settings.REDIS_URL:
        _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
except Exception:
    _redis = None


def rate_limiter(key_prefix: str, limit: int = 60, window_seconds: int = 60) -> Callable:
    """Simple rate limiter dependency.

    Prioritizes Redis when available; falls back to in-memory per-process window.
    Key is built from user_id (if present) or client IP, plus a static prefix.
    """

    async def _dependency(request: Request, principal: Principal = Depends(get_principal)) -> None:  # type: ignore
        user_or_ip = (getattr(principal, "user_id", None) if principal else None) or request.client.host or "anon"
        key = f"rl:{key_prefix}:{user_or_ip}"

        # Redis path
        if _redis is not None:
            try:
                pipe = _redis.pipeline()
                pipe.incr(key, 1)
                pipe.expire(key, window_seconds)
                current, _ = pipe.execute()
                if int(current) > int(limit):
                    raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
                return
            except Exception:
                # fall through to memory
                pass

        # In-memory fallback (best-effort; per-process only)
        now = time.time()
        count, reset_at = _memory_counts.get(key, (0, now + window_seconds))
        if now > reset_at:
            count, reset_at = 0, now + window_seconds
        count += 1
        _memory_counts[key] = (count, reset_at)
        if count > limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    return _dependency


