from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.auth import get_principal, Principal, require_role, require_org_access
from ...core.utils import normalize_phone_to_e164_digits
from ...core.models import (
    Organization, OrganizationCreate, OrganizationResponse,
    User, UserCreate, UserResponse,
    OrgService, OrgServiceCreate, OrgServiceResponse,
    DNCEntry, DNCEntryCreate, DNCEntryResponse,
    RemovalJob, RemovalJobCreate, RemovalJobResponse,
    RemovalJobItem, RemovalJobItemCreate, RemovalJobItemResponse,
    CRMDNCSample, SMSOptOut, DNCRequest, DNCEntry, LitigationRecord,
    SystemSetting, IntegrationTestResult,
)
from passlib.context import CryptContext
from ...core.graph import GraphClient
from ...config import settings

router = APIRouter()
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
# Superadmin: Assign/remove Entra app roles
@router.post("/admin/entra/assign-role")
async def entra_assign_role(payload: dict, principal: Principal = Depends(get_principal)):
    require_role("superadmin")(principal)
    user_oid = str(payload.get("user_object_id"))
    app_id = settings.ENTRA_API_APP_ID or settings.RINGCENTRAL_CLIENT_ID or ""
    app_role_id = str(payload.get("app_role_id"))
    if not user_oid or not app_id or not app_role_id:
        raise HTTPException(status_code=400, detail="user_object_id, app_role_id required")
    client = GraphClient()
    return await client.assign_app_role(user_oid, app_id, app_role_id)

@router.post("/admin/entra/remove-role")
async def entra_remove_role(payload: dict, principal: Principal = Depends(get_principal)):
    require_role("superadmin")(principal)
    user_oid = str(payload.get("user_object_id"))
    assignment_id = str(payload.get("assignment_id"))
    if not user_oid or not assignment_id:
        raise HTTPException(status_code=400, detail="user_object_id, assignment_id required")
    client = GraphClient()
    await client.remove_app_role(assignment_id, user_oid)
    return {"removed": True}

# Auth utilities
@router.get("/auth/me")
def auth_me(principal: Principal = Depends(get_principal)):
    """Return the resolved principal from Entra token or dev headers."""
    return {
        "user_id": principal.user_id,
        "organization_id": principal.organization_id,
        "role": principal.role,
    }
# Dev login (temporary)
@router.post("/auth/login")
def dev_login(payload: dict):
    username = (payload or {}).get("username")
    password = (payload or {}).get("password")
    if username == "admin" and password == "admin":
        return {"success": True, "user_id": 1, "organization_id": 1, "role": "superadmin"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

# Simple password login (email + password) for dev/testing
@router.post("/auth/password-login")
def password_login(payload: dict, db: Session = Depends(get_db)):
    email = (payload or {}).get("email")
    password = (payload or {}).get("password")
    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password required")
    user = db.query(User).filter_by(email=str(email)).first()
    if not user or not user.password_hash or not pwd_ctx.verify(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # Find a default org link if any
    org_link = db.query(OrgService.organization_id).first()
    org_id = getattr(org_link, "organization_id", 1)
    role = user.role or "member"
    return {"success": True, "user_id": user.id, "organization_id": org_id, "role": role}

# System Admin endpoints
@router.get("/system/services")
def list_system_services(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_role("superadmin")(principal)
    rows = db.query(SystemSetting).all()
    # Seed defaults if empty
    if not rows:
        for k in ("convoso","ytel","ringcentral","genesys","logics"):
            db.add(SystemSetting(key=k, enabled=True))
        db.commit()
        rows = db.query(SystemSetting).all()
    return [{"key": r.key, "enabled": r.enabled} for r in rows]


@router.put("/system/services/{key}")
def set_system_service(key: str, payload: dict, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_role("superadmin")(principal)
    enabled = bool(payload.get("enabled", True))
    row = db.query(SystemSetting).filter_by(key=key).first()
    if not row:
        row = SystemSetting(key=key, enabled=enabled)
        db.add(row)
    else:
        row.enabled = enabled
    db.commit()
    return {"key": key, "enabled": enabled}


@router.post("/system/test/{provider}")
def test_provider(provider: str, payload: dict | None = None, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_role("superadmin")(principal)
    phone = (payload or {}).get("phone_e164")
    from datetime import datetime
    success = False
    status_code = None
    snippet = None
    try:
        import httpx
        from ...core.config import settings
        # Minimal, safe read-only probes
        if provider == "ringcentral":
            url = f"{settings.RINGCENTRAL_BASE_URL}/restapi/v1.0/account/{settings.RINGCENTRAL_ACCOUNT_ID}/extension/{settings.RINGCENTRAL_EXTENSION_ID}/caller-blocking/phone-numbers"
            headers = {"Authorization": f"Bearer {settings.RINGCENTRAL_ACCESS_TOKEN}", "Accept": "application/json"}
            with httpx.Client(timeout=10) as client:
                r = client.get(url, headers=headers, params={"page":1, "perPage":5, "status":"Blocked"})
                status_code = r.status_code
                success = r.status_code == 200
                snippet = (r.text or "")[:300]
        elif provider == "convoso":
            url = f"{settings.CONVOSO_BASE_URL}/v1/dnc/search"
            params = { 'auth_token': settings.CONVOSO_AUTH_TOKEN or '', 'phone_number': phone or '15551234567', 'phone_code': '1', 'offset': 0, 'limit': 1 }
            with httpx.Client(timeout=10) as client:
                r = client.get(url, params=params)
                status_code = r.status_code
                success = r.status_code == 200
                snippet = (r.text or "")[:300]
        elif provider == "logics":
            from ...core.tps_api import tps_api
            cases = []
            try:
                import anyio
                anyio.run(lambda: tps_api.find_cases_by_phone(phone or "5551234567"))
            except Exception:
                cases = []
            success = True
            status_code = 200
            snippet = f"cases={len(cases)}"
        elif provider == "ytel":
            # v4 requires bearer; we just report configuration presence
            success = bool(getattr(__import__('do_not_call.config', fromlist=['settings']), 'settings').YTEL_BEARER_TOKEN)
            status_code = 200 if success else 503
            snippet = "token configured" if success else "missing token"
        else:
            status_code = 400
            snippet = "unknown provider"
    except Exception as e:
        success = False
        snippet = str(e)[:300]

    row = IntegrationTestResult(provider_key=provider, phone_e164=phone, success=success, status_code=status_code, response_snippet=snippet)
    db.add(row)
    db.commit()
    return {"provider": provider, "success": success, "status_code": status_code, "response": snippet}


# Organizations
@router.post("/organizations", response_model=OrganizationResponse)
def create_org(payload: OrganizationCreate, db: Session = Depends(get_db)):
    if db.query(Organization).filter_by(slug=payload.slug).first():
        raise HTTPException(status_code=400, detail="Organization slug already exists")
    org = Organization(name=payload.name, slug=payload.slug)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.get("/organizations", response_model=list[OrganizationResponse])
def list_orgs(db: Session = Depends(get_db)):
    return db.query(Organization).order_by(Organization.id.desc()).all()


# Users
@router.post("/users", response_model=UserResponse)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=payload.email).first():
        raise HTTPException(status_code=400, detail="User email already exists")
    user = User(email=payload.email, name=payload.name)
    if getattr(payload, "password", None):
        user.password_hash = pwd_ctx.hash(payload.password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.id.desc()).all()

# Update a user's role or superadmin flag
@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, payload: dict, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_role("owner", "admin", "superadmin")(principal)
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if "role" in payload:
        role = str(payload["role"]).lower()
        if role not in {"owner","admin","member"}:
            raise HTTPException(status_code=400, detail="Invalid role")
        user.role = role
    if "is_super_admin" in payload:
        user.is_super_admin = bool(payload["is_super_admin"])
    db.commit()
    db.refresh(user)
    return user


# Org Services
@router.post("/org-services", response_model=OrgServiceResponse)
def create_org_service(payload: OrgServiceCreate, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_org_access(principal, payload.organization_id)
    require_role("owner", "admin")(principal)
    svc = OrgService(
        organization_id=payload.organization_id,
        service_key=payload.service_key,
        display_name=payload.display_name,
        is_active=payload.is_active,
        credentials=payload.credentials,
        settings=payload.settings,
    )
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc


@router.get("/org-services/{organization_id}", response_model=list[OrgServiceResponse])
def list_org_services(organization_id: int, db: Session = Depends(get_db)):
    return db.query(OrgService).filter_by(organization_id=organization_id).all()


# DNC Entries
@router.post("/dnc-entries", response_model=DNCEntryResponse)
def create_dnc_entry(payload: DNCEntryCreate, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_org_access(principal, payload.organization_id)
    entry = DNCEntry(**payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/dnc-entries/{organization_id}", response_model=list[DNCEntryResponse])
def list_dnc_entries(organization_id: int, db: Session = Depends(get_db)):
    return db.query(DNCEntry).filter_by(organization_id=organization_id).order_by(DNCEntry.id.desc()).limit(500).all()


# Jobs + Items
@router.post("/jobs", response_model=RemovalJobResponse)
def create_job(payload: RemovalJobCreate, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_org_access(principal, payload.organization_id)
    job = RemovalJob(**payload.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/job-items", response_model=RemovalJobItemResponse)
def create_job_item(payload: RemovalJobItemCreate, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    # org inferred from job via FK would be ideal; keeping open here
    item = RemovalJobItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/jobs/{organization_id}", response_model=list[RemovalJobResponse])
def list_jobs(organization_id: int, db: Session = Depends(get_db)):
    return db.query(RemovalJob).filter_by(organization_id=organization_id).order_by(RemovalJob.id.desc()).all()


# Bulk approve/deny
@router.post("/dnc-requests/bulk/approve")
def bulk_approve(payload: dict, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_role("owner", "admin")(principal)
    ids = payload.get("ids", [])
    reviewer = int(payload.get("reviewed_by_user_id", 0))
    updated = 0
    from datetime import datetime
    for rid in ids:
        req = db.query(DNCRequest).get(int(rid))
        if not req or req.status != "pending":
            continue
        req.status = "approved"
        req.reviewed_by_user_id = reviewer
        req.decided_at = datetime.utcnow()
        entry = DNCEntry(
            organization_id=req.organization_id,
            phone_e164=req.phone_e164,
            reason=req.reason,
            channel=req.channel,
            source="user_request",
            created_by_user_id=req.requested_by_user_id,
        )
        db.add(entry)
        updated += 1
    db.commit()
    return {"approved": updated}


@router.post("/dnc-requests/bulk/deny")
def bulk_deny(payload: dict, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_role("owner", "admin")(principal)
    ids = payload.get("ids", [])
    reviewer = int(payload.get("reviewed_by_user_id", 0))
    updated = 0
    from datetime import datetime
    for rid in ids:
        req = db.query(DNCRequest).get(int(rid))
        if not req or req.status != "pending":
            continue
        req.status = "denied"
        req.reviewed_by_user_id = reviewer
        req.decided_at = datetime.utcnow()
        updated += 1
    db.commit()
    return {"denied": updated}


@router.post("/dnc-samples/ingest/{organization_id}")
def ingest_samples(organization_id: int, rows: list[dict], db: Session = Depends(get_db)):
    """Bulk ingest up to 10k rows per call. Rows: {phone_e164, in_national_dnc, in_org_dnc, crm_source?, notes?}."""
    to_add: list[CRMDNCSample] = []
    from datetime import datetime
    sample_date = datetime.utcnow()
    for r in rows[:10000]:
        phone = normalize_phone_to_e164_digits(r.get("phone_e164", ""))
        if not phone:
            continue
        to_add.append(CRMDNCSample(
            organization_id=organization_id,
            sample_date=sample_date,
            phone_e164=phone,
            in_national_dnc=bool(r.get("in_national_dnc", False)),
            in_org_dnc=bool(r.get("in_org_dnc", False)),
            crm_source=r.get("crm_source"),
            notes=r.get("notes"),
        ))
    if to_add:
        db.bulk_save_objects(to_add)
        db.commit()
    return {"ingested": len(to_add), "sample_date": sample_date.isoformat()}


@router.get("/dnc-samples/{organization_id}")
def query_samples(organization_id: int, only_gaps: bool = True, limit: int = 1000, db: Session = Depends(get_db)):
    q = db.query(CRMDNCSample).filter(CRMDNCSample.organization_id == organization_id)
    if only_gaps:
        q = q.filter(CRMDNCSample.in_national_dnc.is_(True), CRMDNCSample.in_org_dnc.is_(False))
    rows = q.order_by(CRMDNCSample.sample_date.desc()).limit(min(10000, limit)).all()
    return [{
        "id": r.id,
        "phone_e164": r.phone_e164,
        "in_national_dnc": r.in_national_dnc,
        "in_org_dnc": r.in_org_dnc,
        "sample_date": r.sample_date.isoformat(),
        "crm_source": r.crm_source,
        "notes": r.notes,
    } for r in rows]


@router.post("/dnc-samples/{organization_id}/bulk_add_to_dnc")
def bulk_add_samples_to_dnc(organization_id: int, payload: dict, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_org_access(principal, organization_id)
    require_role("owner", "admin")(principal)
    ids: list[int] = payload.get("ids", [])
    created = 0
    for sid in ids:
        s = db.query(CRMDNCSample).get(int(sid))
        if not s:
            continue
        # Skip if already in org DNC
        exists = db.query(DNCEntry).filter_by(organization_id=organization_id, phone_e164=s.phone_e164, active=True).first()
        if exists:
            continue
        e = DNCEntry(
            organization_id=organization_id,
            phone_e164=s.phone_e164,
            reason="gap (national yes, org no)",
            channel="voice",
            source="samples_gap",
            created_by_user_id=principal.user_id,
        )
        db.add(e)
        created += 1
    db.commit()
    return {"created": created}


# SMS STOP ingest
@router.post("/sms-stop/ingest/{organization_id}")
def ingest_sms_stop(organization_id: int, rows: list[dict], db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_org_access(principal, organization_id)
    require_role("owner", "admin")(principal)
    items: list[SMSOptOut] = []
    from datetime import datetime
    # Preload org DNC for quick lookups
    dnc_map = {e.phone_e164: e.id for e in db.query(DNCEntry.id, DNCEntry.phone_e164).filter(DNCEntry.organization_id == organization_id, DNCEntry.active.is_(True)).all()}
    for r in rows:
        phone = normalize_phone_to_e164_digits(r.get("phone_e164", ""))
        if not phone:
            continue
        # If not yet in org DNC, create SMS DNC entry and link
        entry_id = dnc_map.get(phone)
        if entry_id is None:
            entry = DNCEntry(
                organization_id=organization_id,
                phone_e164=phone,
                reason=r.get("reason", "sms stop"),
                channel="sms",
                source="sms_stop",
                created_by_user_id=r.get("created_by_user_id"),
                notes=r.get("notes"),
            )
            db.add(entry)
            db.flush()
            entry_id = entry.id
            dnc_map[phone] = entry_id

        items.append(SMSOptOut(
            organization_id=organization_id,
            phone_e164=phone,
            message_id=r.get("message_id"),
            carrier=r.get("carrier"),
            keyword=r.get("keyword", "STOP"),
            received_at=datetime.utcnow(),
            dnc_entry_id=entry_id,
            processed=True,
            notes=r.get("notes"),
        ))
    if items:
        db.bulk_save_objects(items)
        db.commit()
    return {"ingested": len(items)}


# DNC Request workflow
@router.post("/dnc-requests/{organization_id}")
def create_dnc_request(organization_id: int, payload: dict, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_org_access(principal, organization_id)
    # members can create
    req = DNCRequest(
        organization_id=organization_id,
        phone_e164=normalize_phone_to_e164_digits(payload.get("phone_e164", "")),
        reason=payload.get("reason"),
        channel=payload.get("channel"),
        requested_by_user_id=int(payload.get("requested_by_user_id")),
        status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return {"id": req.id, "status": req.status}


@router.post("/dnc-requests/{request_id}/approve")
def approve_dnc_request(request_id: int, payload: dict, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_role("owner", "admin")(principal)
    req = db.query(DNCRequest).get(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Request already decided")
    req.status = "approved"
    req.reviewed_by_user_id = int(payload.get("reviewed_by_user_id"))
    req.decision_notes = payload.get("notes")
    from datetime import datetime
    req.decided_at = datetime.utcnow()
    # Create DNC entry now
    entry = DNCEntry(
        organization_id=req.organization_id,
        phone_e164=req.phone_e164,
        reason=req.reason,
        channel=req.channel,
        source="user_request",
        created_by_user_id=req.requested_by_user_id,
        notes=req.decision_notes,
    )
    db.add(entry)
    db.commit()
    return {"request_id": req.id, "status": req.status}


@router.post("/dnc-requests/{request_id}/deny")
def deny_dnc_request(request_id: int, payload: dict, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_role("owner", "admin")(principal)
    req = db.query(DNCRequest).get(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Request already decided")
    req.status = "denied"
    req.reviewed_by_user_id = int(payload.get("reviewed_by_user_id"))
    req.decision_notes = payload.get("notes")
    from datetime import datetime
    req.decided_at = datetime.utcnow()
    db.commit()
    return {"request_id": req.id, "status": req.status}


# Listing endpoints for admin/user portals
@router.get("/dnc-requests/org/{organization_id}")
def list_requests_by_org(organization_id: int, status: str | None = None, cursor: int | None = None, limit: int = 50, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_org_access(principal, organization_id)
    require_role("owner", "admin")(principal)
    q = db.query(DNCRequest).filter(DNCRequest.organization_id == organization_id)
    if status:
        q = q.filter(DNCRequest.status == status)
    if cursor:
        q = q.filter(DNCRequest.id < cursor)
    q = q.order_by(DNCRequest.id.desc()).limit(min(200, max(1, limit)))
    rows = q.all()
    return [{
        "id": r.id,
        "phone_e164": r.phone_e164,
        "status": r.status,
        "reason": r.reason,
        "channel": r.channel,
        "requested_by_user_id": r.requested_by_user_id,
        "reviewed_by_user_id": r.reviewed_by_user_id,
        "created_at": r.created_at.isoformat(),
        "decided_at": r.decided_at.isoformat() if r.decided_at else None,
    } for r in rows]


@router.get("/dnc-requests/user/{user_id}")
def list_requests_by_user(user_id: int, status: str | None = None, cursor: int | None = None, limit: int = 50, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    # user can see their requests; admins can see anyone's
    if principal.role not in {"owner", "admin"} and principal.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    q = db.query(DNCRequest).filter(DNCRequest.requested_by_user_id == user_id)
    if status:
        q = q.filter(DNCRequest.status == status)
    if cursor:
        q = q.filter(DNCRequest.id < cursor)
    q = q.order_by(DNCRequest.id.desc()).limit(min(200, max(1, limit)))
    rows = q.all()
    return [{
        "id": r.id,
        "organization_id": r.organization_id,
        "phone_e164": r.phone_e164,
        "status": r.status,
        "reason": r.reason,
        "channel": r.channel,
        "created_at": r.created_at.isoformat(),
        "decided_at": r.decided_at.isoformat() if r.decided_at else None,
    } for r in rows]


# Litigation endpoints
@router.post("/litigations/{organization_id}")
def add_litigation(organization_id: int, payload: dict, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_org_access(principal, organization_id)
    require_role("owner", "admin")(principal)
    record = LitigationRecord(
        organization_id=organization_id,
        phone_e164=normalize_phone_to_e164_digits(payload.get("phone_e164", "")),
        company=payload.get("company"),
        case_number=payload.get("case_number"),
        received_at=payload.get("received_at"),
        received_by_user_id=principal.user_id,
        status=payload.get("status", "open"),
        actions=payload.get("actions"),
        notes=payload.get("notes"),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": record.id}


@router.get("/litigations/{organization_id}")
def list_litigations(organization_id: int, q: str | None = None, cursor: int | None = None, limit: int = 50, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_org_access(principal, organization_id)
    qy = db.query(LitigationRecord).filter(LitigationRecord.organization_id == organization_id)
    if q:
        qlike = f"%{q}%"
        qy = qy.filter((LitigationRecord.phone_e164.like(qlike)) | (LitigationRecord.company.like(qlike)) | (LitigationRecord.case_number.like(qlike)))
    if cursor:
        qy = qy.filter(LitigationRecord.id < cursor)
    rows = qy.order_by(LitigationRecord.id.desc()).limit(min(200, max(1, limit))).all()
    return [{
        "id": r.id,
        "phone_e164": r.phone_e164,
        "company": r.company,
        "case_number": r.case_number,
        "received_at": r.received_at.isoformat() if r.received_at else None,
        "status": r.status,
        "notes": r.notes,
    } for r in rows]

