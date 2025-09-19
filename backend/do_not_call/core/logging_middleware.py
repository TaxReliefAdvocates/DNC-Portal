from __future__ import annotations

import json
import time
from typing import Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from ..config import settings


class JsonRequestLogger(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        start = time.time()
        cid = request.headers.get("X-Correlation-Id")
        if not cid:
            import uuid
            cid = str(uuid.uuid4())
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise
        finally:
            duration_ms = int((time.time() - start) * 1000)
            principal = getattr(request.state, "principal", None)
            log = {
                "level": "INFO",
                "message": "request",
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "duration_ms": duration_ms,
                "org_id": getattr(principal, "organization_id", None),
                "user_id": getattr(principal, "user_id", None),
                "role": getattr(principal, "role", None),
                "cid": cid,
            }
            try:
                print(json.dumps(log))
            except Exception:
                pass
        response.headers["X-Correlation-Id"] = cid
        return response


