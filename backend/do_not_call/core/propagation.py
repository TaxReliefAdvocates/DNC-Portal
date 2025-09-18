from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional
from datetime import datetime

from sqlalchemy.orm import Session

from .models import PropagationAttempt, SystemSetting


async def track_provider_attempt(
    db: Session,
    *,
    organization_id: int,
    service_key: str,
    phone_e164: str,
    actor_user_id: Optional[int] = None,
    request_context: Optional[dict[str, Any]] = None,
    call: Callable[[], Awaitable[Any]] | None = None,
) -> dict[str, Any]:
    """Create a PropagationAttempt row for any provider call and update with the result.

    - Creates attempt with status=pending
    - Executes the provided async callable (if given)
    - Updates attempt to success/failed with response/error
    - Returns a small dict summary (status, attempt_id)
    """
    # Skip if provider disabled
    row = db.query(SystemSetting).filter(SystemSetting.key == service_key).first()
    if row is not None and not bool(row.enabled):
        return {"skipped": True, "reason": "provider disabled", "service_key": service_key}

    attempt = PropagationAttempt(
        organization_id=int(organization_id or 0),
        job_item_id=None,
        phone_e164=str(phone_e164),
        service_key=str(service_key),
        attempt_no=1,
        status="pending",
        request_payload={
            "actor_user_id": actor_user_id,
            "context": request_context or {},
        },
        started_at=datetime.utcnow(),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    try:
        result: Any = None
        if call is not None:
            result = await call()
        attempt.status = "success"
        attempt.response_payload = result if isinstance(result, (dict, list)) else {"result": str(result)} if result is not None else None
        attempt.finished_at = datetime.utcnow()
        db.commit()
        return {"status": "success", "attempt_id": attempt.id}
    except Exception as e:
        attempt.status = "failed"
        attempt.error_message = str(e)
        attempt.finished_at = datetime.utcnow()
        db.commit()
        return {"status": "failed", "attempt_id": attempt.id, "error": str(e)}


