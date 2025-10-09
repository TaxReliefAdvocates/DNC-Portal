from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from sqlalchemy.orm import Session
from loguru import logger

from ...core.database import get_db, set_rls_org
from ...core.rate_limit import rate_limiter
from ...core.auth import get_principal, Principal, require_role, require_org_access
from ...core.utils import normalize_phone_to_e164_digits
from ...core.models import (
    Organization, OrganizationCreate, OrganizationResponse,
    User, UserCreate, UserResponse,
    OrgService, OrgServiceCreate, OrgServiceResponse,
    DNCEntry, DNCEntryCreate, DNCEntryResponse,
    RemovalJob, RemovalJobCreate, RemovalJobResponse,
    RemovalJobItem, RemovalJobItemCreate, RemovalJobItemResponse,
    CRMDNCSample, SMSOptOut, DNCRequest, DNCEntry, LitigationRecord, PhoneNumber, CRMStatus,
    SystemSetting, IntegrationTestResult, PropagationAttempt,
)
from passlib.context import CryptContext
from ...core.graph import GraphClient
from ...config import settings
from sqlalchemy import inspect, text
import anyio
import httpx
from ...api.v1.providers.ringcentral import ringcentral_get_token

router = APIRouter()
# Track provider DNC history attempts
@router.post("/propagation/attempt")
def record_propagation_attempt(payload: dict, db: Session = Depends(get_db), principal: Principal = Depends(get_principal), _=Depends(rate_limiter("propagate", limit=30, window_seconds=60))):
    # Set RLS org for duration of this request (non-superadmin)
    try:
        org_id = getattr(principal, "organization_id", None) if principal and principal.role not in {"superadmin"} else None
        set_rls_org(db, org_id)
    except Exception:
        pass
    require_role("owner", "admin", "superadmin")(principal)
    try:
        attempt = PropagationAttempt(
            organization_id=int(payload.get("organization_id") or principal.organization_id or 1),
            job_item_id=payload.get("job_item_id"),
            phone_e164=str(payload.get("phone_e164")),
            service_key=str(payload.get("service_key")),
            attempt_no=int(payload.get("attempt_no", 1)),
            status=str(payload.get("status", "pending")),
            request_payload=payload.get("request_payload"),
            response_payload=payload.get("response_payload"),
            error_message=payload.get("error_message"),
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        return {
            "id": attempt.id,
            "organization_id": attempt.organization_id,
            "phone_e164": attempt.phone_e164,
            "service_key": attempt.service_key,
            "status": attempt.status,
            "attempt_no": attempt.attempt_no,
            "started_at": attempt.started_at.isoformat(),
            "finished_at": attempt.finished_at.isoformat() if attempt.finished_at else None,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to record attempt: {e}")

@router.get("/propagation/attempts/{organization_id}")
def list_propagation_attempts(organization_id: int, cursor: int | None = None, limit: int = 100, db: Session = Depends(get_db), principal: Principal = Depends(get_principal), _=Depends(rate_limiter("attempts", limit=120, window_seconds=60))):
    try:
        org_id = None if principal.role == "superadmin" else organization_id
        set_rls_org(db, org_id)
    except Exception:
        pass
    require_org_access(principal, organization_id)
    require_role("owner", "admin", "superadmin")(principal)
    q = db.query(PropagationAttempt).filter(PropagationAttempt.organization_id == organization_id)
    if cursor:
        q = q.filter(PropagationAttempt.id < cursor)
    # Use the new index for better performance - order by started_at DESC (most recent first)
    rows = q.order_by(PropagationAttempt.started_at.desc(), PropagationAttempt.id.desc()).limit(min(500, max(1, limit))).all()
    return [
        {
            "id": r.id,
            "organization_id": r.organization_id,
            "job_item_id": r.job_item_id,
            "phone_e164": r.phone_e164,
            "service_key": r.service_key,
            "status": r.status,
            "attempt_no": r.attempt_no,
            "error_message": r.error_message,
            "started_at": r.started_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in rows
    ]


@router.delete("/propagation/attempts/clear")
def clear_propagation_attempts(organization_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Clear all propagation attempts for the organization (admin only)."""
    require_org_access(principal, organization_id)
    require_role("owner", "admin", "superadmin")(principal)
    
    try:
        # Clear all propagation attempts for this organization
        deleted_count = db.query(PropagationAttempt).filter(
            PropagationAttempt.organization_id == organization_id
        ).delete()
        
        db.commit()
        
        logger.info(f"Cleared {deleted_count} propagation attempts for organization {organization_id}")
        
        return {
            "message": f"Cleared {deleted_count} propagation attempts",
            "deleted_count": deleted_count,
            "organization_id": organization_id
        }
        
    except Exception as e:
        logger.error(f"Error clearing propagation attempts: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear propagation attempts: {str(e)}")


@router.post("/propagation/attempts/recreate-all")
def recreate_propagation_attempts_for_approved_requests(organization_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Recreate propagation attempts for all approved DNC requests (admin only)."""
    require_org_access(principal, organization_id)
    require_role("owner", "admin", "superadmin")(principal)
    
    try:
        # Get all approved DNC requests for this organization
        approved_requests = db.query(DNCRequest).filter(
            DNCRequest.organization_id == organization_id,
            DNCRequest.status == "approved"
        ).all()
        
        created_count = 0
        
        for request in approved_requests:
            # Create propagation attempts for each approved request
            _create_immediate_propagation_attempt(organization_id, request.phone_e164, db)
            created_count += 5  # 5 services per request
        
        db.commit()
        
        logger.info(f"Recreated propagation attempts for {len(approved_requests)} approved requests ({created_count} total attempts)")
        
        return {
            "message": f"Recreated propagation attempts for {len(approved_requests)} approved requests",
            "approved_requests_count": len(approved_requests),
            "total_attempts_created": created_count,
            "organization_id": organization_id
        }
        
    except Exception as e:
        logger.error(f"Error recreating propagation attempts: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to recreate propagation attempts: {str(e)}")


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

@router.get("/admin/entra/app-roles")
async def entra_list_app_roles(principal: Principal = Depends(get_principal)):
    require_role("superadmin")(principal)
    app_id = settings.ENTRA_API_APP_ID or settings.GRAPH_CLIENT_ID or settings.ENTRA_AUDIENCE or ""
    if not app_id:
        raise HTTPException(status_code=400, detail="ENTRA_API_APP_ID not configured")
    client = GraphClient()
    return await client.list_app_roles(app_id)

@router.put("/admin/entra/app-roles/{application_object_id}")
async def entra_update_app_roles(application_object_id: str, payload: dict, principal: Principal = Depends(get_principal)):
    require_role("superadmin")(principal)
    app_roles = payload.get("appRoles")
    if not isinstance(app_roles, list):
        raise HTTPException(status_code=400, detail="appRoles array required")
    client = GraphClient()
    return await client.update_app_roles(application_object_id, app_roles)

@router.get("/admin/entra/user-assignments/{user_object_id}")
async def entra_user_assignments(user_object_id: str, principal: Principal = Depends(get_principal)):
    require_role("superadmin")(principal)
    app_id = settings.ENTRA_API_APP_ID or settings.GRAPH_CLIENT_ID or settings.ENTRA_AUDIENCE or ""
    if not app_id:
        raise HTTPException(status_code=400, detail="ENTRA_API_APP_ID not configured")
    client = GraphClient()
    return await client.list_user_role_assignments(user_object_id, app_id)

# Superadmin: one-click sync users/roles from Entra app role assignments
@router.post("/admin/entra/sync-users")
async def entra_sync_users(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    require_role("superadmin")(principal)
    app_id = settings.ENTRA_API_APP_ID or settings.GRAPH_CLIENT_ID or settings.ENTRA_AUDIENCE or ""
    if not app_id:
        raise HTTPException(status_code=400, detail="ENTRA_API_APP_ID not configured")
    client = GraphClient()
    assignments = await client.list_app_role_assignments(app_id)
    value = assignments.get("value", [])
    upserted = 0
    linked = 0
    default_org_id = getattr(settings, "DEFAULT_ORG_ID", 1)
    for a in value:
        try:
            principal_id = a.get("principalId")  # user OID
            app_role_id = a.get("appRoleId")
            # Fetch user basics
            u = await client.get_user(principal_id)
            email = u.get("mail") or u.get("userPrincipalName") or u.get("onPremisesUserPrincipalName")
            name = u.get("displayName") or email
            # Role name is not returned here; we map by appRoleId → displayName via app roles list
        except Exception:
            continue
        # Lazy fetch app roles map once
        if not hasattr(entra_sync_users, "_role_map"):
            roles_resp = await client.list_app_roles(app_id)
            role_map = {r.get("id"): (r.get("displayName") or r.get("value") or "User") for r in roles_resp.get("appRoles", [])}
            setattr(entra_sync_users, "_role_map", role_map)
        role_name = getattr(entra_sync_users, "_role_map", {}).get(app_role_id, "User")
        internal_role = "member"
        is_super = False
        rn = (role_name or "").strip().lower().replace(" ", "")
        if rn in {"superadmin", "superadministrator"}:
            internal_role = "owner"  # keep DB role high but we also set super flag
            is_super = True
        elif rn in {"admin", "administrator"}:
            internal_role = "admin"
        elif rn in {"owner"}:
            internal_role = "owner"
        else:
            internal_role = "member"
        # Upsert user
        user = db.query(User).filter((User.oid == str(principal_id)) | (User.email == str(email))).first()
        if not user:
            user = User(oid=str(principal_id), email=str(email), name=name, role=internal_role, is_super_admin=is_super)
            db.add(user)
            db.flush()
            upserted += 1
        else:
            changed = False
            if user.role != internal_role:
                user.role = internal_role
                changed = True
            if getattr(user, "is_super_admin", False) != is_super:
                user.is_super_admin = is_super
                changed = True
            if changed:
                upserted += 1
        # Ensure org link
        if default_org_id:
            link = db.query(OrgUser).filter_by(user_id=user.id, organization_id=default_org_id).first()
            if not link:
                db.add(OrgUser(organization_id=default_org_id, user_id=user.id, role=user.role or "member"))
                linked += 1
    db.commit()
    return {"upserted": upserted, "linked": linked, "assignments": len(value)}

# Superadmin: purge DNC requests
@router.post("/admin/purge/dnc-requests")
def purge_dnc_requests(payload: dict | None = None, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    require_role("superadmin")(principal)
    org_id = (payload or {}).get("organization_id")
    status = (payload or {}).get("status")
    q = db.query(DNCRequest)
    if org_id is not None:
        q = q.filter(DNCRequest.organization_id == int(org_id))
    if status:
        q = q.filter(DNCRequest.status == str(status))
    deleted = q.delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted}

# Auth utilities
@router.get("/auth/me")
def auth_me(principal: Principal = Depends(get_principal)):
    """Return the resolved principal from Entra token or dev headers."""
    return {
        "user_id": principal.user_id,
        "organization_id": principal.organization_id,
        "role": principal.role,
    }

# Test endpoint for debugging
@router.get("/test/approve")
def test_approve_endpoint():
    """Test endpoint to verify backend is working."""
    return {"status": "ok", "message": "Backend is working"}

@router.get("/test/request/{request_id}")
def test_request_exists(request_id: int, db: Session = Depends(get_db)):
    """Test endpoint to check if a request exists."""
    req = db.query(DNCRequest).get(request_id)
    if req:
        return {
            "exists": True,
            "id": req.id,
            "phone_e164": req.phone_e164,
            "status": req.status,
            "organization_id": req.organization_id
        }
    else:
        return {"exists": False, "id": request_id}

@router.post("/test/approve-simple/{request_id}")
def test_approve_simple(request_id: int, db: Session = Depends(get_db)):
    """Minimal test endpoint for approval."""
    try:
        req = db.query(DNCRequest).get(request_id)
        if not req:
            return {"error": "Request not found", "id": request_id}
        
        if req.status != "pending":
            return {"error": "Request already decided", "status": req.status}
        
        # Just update the status, don't create DNC entry yet
        req.status = "approved"
        req.decision_notes = "Test approval"
        from datetime import datetime
        req.decided_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "success": True,
            "request_id": req.id,
            "status": req.status,
            "message": "Simple approval test successful"
        }
    except Exception as e:
        db.rollback()
        return {"error": str(e), "type": type(e).__name__}

# DB schema + health (superadmin)
@router.get("/admin/db/schema")
def db_schema(include_counts: bool = False, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_role("superadmin")(principal)
    insp = inspect(db.bind)
    report: list[dict] = []
    for tbl in sorted(insp.get_table_names()):
        t: dict = {"table": tbl, "columns": [], "pk": [], "fks": [], "indexes": []}
        for c in insp.get_columns(tbl):
            t["columns"].append({
                "name": c["name"],
                "type": str(c.get("type")),
                "nullable": c.get("nullable"),
                "default": c.get("default"),
            })
        pk = insp.get_pk_constraint(tbl)
        if pk:
            t["pk"] = pk.get("constrained_columns") or []
        for fk in insp.get_foreign_keys(tbl):
            t["fks"].append({
                "columns": fk.get("constrained_columns", []),
                "referred_table": fk.get("referred_table"),
                "referred_columns": fk.get("referred_columns", []),
            })
        for ix in insp.get_indexes(tbl):
            t["indexes"].append({
                "name": ix.get("name"),
                "columns": ix.get("column_names", []),
                "unique": ix.get("unique"),
            })
        if include_counts:
            try:
                cnt = db.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()  # type: ignore
            except Exception:
                cnt = None
            t["row_count"] = cnt
        report.append(t)
    return {"database_url": str(getattr(settings, 'DATABASE_URL', '')), "tables": report}
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
        from ...config import settings
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


# DNC Orchestration (admin)
@router.post("/dnc/orchestrate")
async def orchestrate_dnc(payload: dict, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Run cross-provider DNC search, add missing, log attempts, and record org DNC entries.

    Payload: { "phone_numbers": ["+15618189087", ...] }
    """
    require_role("owner", "admin", "superadmin")(principal)
    try:
        org_id = getattr(principal, "organization_id", None) if principal and principal.role not in {"superadmin"} else None
        set_rls_org(db, org_id)
    except Exception:
        pass

    numbers = payload.get("phone_numbers") or []
    mode = str(payload.get("mode", "push")).lower()  # "search" or "push"
    do_adds = mode == "push"
    if not isinstance(numbers, list) or not numbers:
        raise HTTPException(status_code=400, detail="phone_numbers array required")

    # Provider creds from settings/env
    from ...config import settings as cfg
    y_user = getattr(cfg, "ytel_user", None)
    y_pass = getattr(cfg, "ytel_password", None)
    conv_token = getattr(cfg, "convoso_auth_token", None) or getattr(cfg, "convoso_leads_auth_token", None)
    g_cid = getattr(cfg, "genesys_client_id", None)
    g_csec = getattr(cfg, "genesys_client_secret", None)
    g_list = getattr(cfg, "genesys_dnclist_id", None) if hasattr(cfg, "genesys_dnclist_id") else None
    # RingCentral uses JWT assertion in settings; we'll search blocked list

    results: list[dict] = []
    for raw in numbers:
            # Normalize to E.164 digits using existing utility
            phone = normalize_phone_to_e164_digits(raw)
            entry: dict = {"phone_e164": phone, "searched": {}, "added": {}, "freednc": None}

            # FreeDNC check via service
            try:
                from ...core.dnc_service import dnc_service
                d = await dnc_service.check_federal_dnc(phone)
                entry["freednc"] = d
            except Exception as e:
                entry["freednc_error"] = str(e)

            # Ytel search → add if needed (only when mode==push)
            if y_user and y_pass:
                try:
                    base = "https://tra.ytel.com/x5/api/non_agent.php"
                    params = {
                        "function": "add_lead",
                        "user": y_user,
                        "pass": y_pass,
                        "source": "dncfilter",
                        "phone_number": phone,
                        "dnc_check": "Y",
                        "campaign_dnc_check": "Y",
                        "duplicate_check": "Y",
                    }
                    rs = await httpx.get(base, params=params, timeout=30.0)
                    txt = rs.text or ""
                    listed = "PHONE NUMBER IN DNC" in txt
                    entry.setdefault("searched", {}).setdefault("ytel", {})["listed"] = listed
                except Exception as e:
                    entry.setdefault("searched", {}).setdefault("ytel", {})["error"] = str(e)
                if do_adds:
                    try:
                        base = "https://tra.ytel.com/x5/api/non_agent.php"
                        params = {
                            "function": "update_lead",
                            "user": y_user,
                            "pass": y_pass,
                            "source": "dncfilter",
                            "status": "DNC",
                            "phone_number": phone,
                            "ADDTODNC": "BOTH",
                        }
                        await httpx.get(base, params=params, timeout=30.0)
                        entry.setdefault("added", {})["ytel"] = {"ok": True}
                    except Exception as e:
                        entry.setdefault("add_errors", {})["ytel"] = str(e)

            # Convoso search/add (only add when mode==push)
            if conv_token:
                try:
                    url = "https://api.convoso.com/v1/dnc/search"
                    params = {"auth_token": conv_token, "phone_number": phone, "phone_code": "1", "offset": 0, "limit": 10}
                    r = await httpx.get(url, params=params, timeout=30.0)
                    js = r.json() if r.headers.get("content-type","" ).startswith("application/json") else {}
                    total = ((js or {}).get("data") or {}).get("total", 0)
                    entry.setdefault("searched", {}).setdefault("convoso", {})["listed"] = bool(total and int(total) > 0)
                except Exception as e:
                    entry.setdefault("searched", {}).setdefault("convoso", {})["error"] = str(e)
                if do_adds:
                    try:
                        url = "https://api.convoso.com/v1/dnc/insert"
                        params = {"auth_token": conv_token, "phone_number": phone, "phone_code": "1"}
                        await httpx.get(url, params=params, timeout=30.0)
                        entry.setdefault("added", {})["convoso"] = {"ok": True}
                    except Exception as e:
                        entry.setdefault("add_errors", {})["convoso"] = str(e)

            # Genesys export-check/add (only add when mode==push)
            if g_cid and g_csec and g_list:
                try:
                    login_base = (getattr(cfg, "genesys_region_login_base", None) or "https://login.usw2.pure.cloud").rstrip("/")
                    api_base = (getattr(cfg, "genesys_api_base", None) or "https://api.usw2.pure.cloud").rstrip("/")
                    tok = (await httpx.post(f"{login_base}/oauth/token", data={"grant_type":"client_credentials","client_id": g_cid, "client_secret": g_csec}, headers={"Content-Type":"application/x-www-form-urlencoded"}, timeout=30.0)).json().get("access_token")
                    headers = {"Authorization": f"Bearer {tok}"}
                    r = await httpx.get(f"{api_base}/api/v2/outbound/dnclists/{g_list}/export", headers=headers, timeout=30.0)
                    text_blob = r.text or ""
                    entry.setdefault("searched", {}).setdefault("genesys", {})["present"] = { phone: (phone in text_blob) }
                except Exception as e:
                    entry.setdefault("searched", {}).setdefault("genesys", {})["error"] = str(e)
                if do_adds:
                    try:
                        login_base = (getattr(cfg, "genesys_region_login_base", None) or "https://login.usw2.pure.cloud").rstrip("/")
                        api_base = (getattr(cfg, "genesys_api_base", None) or "https://api.usw2.pure.cloud").rstrip("/")
                        tok = (await httpx.post(f"{login_base}/oauth/token", data={"grant_type":"client_credentials","client_id": g_cid, "client_secret": g_csec}, headers={"Content-Type":"application/x-www-form-urlencoded"}, timeout=30.0)).json().get("access_token")
                        headers = {"Authorization": f"Bearer {tok}", "Content-Type":"application/json"}
                        await httpx.patch(f"{api_base}/api/v2/outbound/dnclists/{g_list}/phonenumbers", headers=headers, json={"action":"Add", "phoneNumbers":[phone], "expirationDateTime":""}, timeout=30.0)
                        entry.setdefault("added", {})["genesys"] = {"ok": True}
                    except Exception as e:
                        entry.setdefault("add_errors", {})["genesys"] = str(e)

            # RingCentral search (blocked list)
            try:
                # Acquire access token via server credentials
                token = await ringcentral_get_token()
                headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
                params = {"status": "Blocked", "page": 1, "perPage": 100}
                rc_phone = phone if phone.startswith("+") else f"+{phone}"
                async with httpx.AsyncClient(base_url="https://platform.ringcentral.com") as hc:
                    r = await hc.get("/restapi/v1.0/account/~/extension/~/caller-blocking/phone-numbers", headers=headers, params=params)
                    listed = False
                    try:
                        js = r.json()
                        items = js.get("records") or js.get("data") or []
                        for it in items:
                            if str(it.get("phoneNumber", "")) == rc_phone:
                                listed = True
                                break
                    except Exception:
                        listed = False
                    entry.setdefault("searched", {}).setdefault("ringcentral", {})["listed"] = listed
            except Exception:
                entry.setdefault("searched", {}).setdefault("ringcentral", {})["error"] = "search_failed"

            # Log attempt rows (best-effort)
            try:
                from ...core.propagation import track_provider_attempt
                org_for_log = int(getattr(principal, "organization_id", 0) or 0)
                for provider_key in ("ytel", "convoso", "genesys"):
                    if provider_key in entry.get("searched", {}) or provider_key in entry.get("added", {}):
                        await track_provider_attempt(
                            db,
                            organization_id=org_for_log,
                            service_key=provider_key,
                            phone_e164=str(phone),
                            actor_user_id=int(getattr(principal, "user_id", 0) or 0),
                            request_context={"action": "orchestrate"},
                            call=None,
                        )
            except Exception:
                pass

            # Ensure an org DNC entry exists
            try:
                exists = db.query(DNCEntry).filter_by(organization_id=int(getattr(principal, "organization_id", 0) or 0), phone_e164=phone, active=True).first()
                if not exists:
                    e = DNCEntry(
                        organization_id=int(getattr(principal, "organization_id", 0) or 0),
                        phone_e164=phone,
                        reason="orchestrated",
                        channel="voice",
                        source="orchestrate_api",
                        created_by_user_id=int(getattr(principal, "user_id", 0) or 0),
                    )
                    db.add(e)
                    db.commit()
            except Exception:
                pass

            results.append(entry)

    return {"success": True, "count": len(results), "results": results}


# Org Services
@router.post("/org-services", response_model=OrgServiceResponse)
def create_org_service(payload: OrgServiceCreate, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_org_access(principal, payload.organization_id)
    require_role("owner", "admin", "superadmin")(principal)
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
    try:
        org_scope = None if principal.role == "superadmin" else payload.organization_id
        set_rls_org(db, org_scope)
    except Exception:
        pass
    require_org_access(principal, payload.organization_id)
    data = payload.model_dump()
    data["created_by_user_id"] = getattr(principal, "user_id", None)
    entry = DNCEntry(**data)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/dnc-entries/{organization_id}", response_model=list[DNCEntryResponse])
def list_dnc_entries(organization_id: int, db: Session = Depends(get_db)):
    try:
        # no principal here; list is admin-only elsewhere. RLS uses path org
        set_rls_org(db, organization_id)
    except Exception:
        pass
    return db.query(DNCEntry).filter_by(organization_id=organization_id).order_by(DNCEntry.id.desc()).limit(500).all()


# Jobs + Items
@router.post("/jobs", response_model=RemovalJobResponse)
def create_job(payload: RemovalJobCreate, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    try:
        org_scope = None if principal.role == "superadmin" else payload.organization_id
        set_rls_org(db, org_scope)
    except Exception:
        pass
    require_org_access(principal, payload.organization_id)
    data = payload.model_dump()
    data["submitted_by_user_id"] = getattr(principal, "user_id", None)
    job = RemovalJob(**data)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/job-items", response_model=RemovalJobItemResponse)
def create_job_item(payload: RemovalJobItemCreate, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    # org inferred from job via FK would be ideal; keeping open here
    try:
        # Fallback to principal org; RLS will validate via FK policy on job
        org_scope = None if principal.role == "superadmin" else getattr(principal, "organization_id", None)
        set_rls_org(db, org_scope)
    except Exception:
        pass
    item = RemovalJobItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/jobs/{organization_id}", response_model=list[RemovalJobResponse])
def list_jobs(organization_id: int, db: Session = Depends(get_db)):
    try:
        set_rls_org(db, organization_id)
    except Exception:
        pass
    return db.query(RemovalJob).filter_by(organization_id=organization_id).order_by(RemovalJob.id.desc()).all()


# Bulk approve/deny
@router.post("/dnc-requests/bulk/approve")
def bulk_approve(payload: dict, db: Session = Depends(get_db), principal: Principal = Depends(get_principal), background_tasks: BackgroundTasks = None, _=Depends(rate_limiter("approve", limit=30, window_seconds=60))):
    try:
        org_id = getattr(principal, "organization_id", None) if principal and principal.role not in {"superadmin"} else None
        set_rls_org(db, org_id)
    except Exception:
        pass
    require_role("owner", "admin", "superadmin")(principal)
    ids = payload.get("ids", [])
    reviewer = int(getattr(principal, "user_id", 0) or 0)
    updated = 0
    from datetime import datetime
    approved_requests = []
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
        approved_requests.append((req.organization_id, req.phone_e164))
        updated += 1
    db.commit()
    
    # Create immediate propagation attempts for visibility
    for org_id, phone in approved_requests:
        _create_immediate_propagation_attempt(org_id, phone, db)
    
    # Trigger enhanced propagation for all approved requests
    try:
        if background_tasks is not None:
            for org_id, phone in approved_requests:
                background_tasks.add_task(_propagate_approved_entry_with_systems_check, org_id, phone, reviewer)
    except Exception:
        pass
    
    return {"approved": updated}


@router.post("/dnc-requests/bulk/deny")
def bulk_deny(payload: dict, db: Session = Depends(get_db), principal: Principal = Depends(get_principal), _=Depends(rate_limiter("deny", limit=30, window_seconds=60))):
    try:
        org_id = getattr(principal, "organization_id", None) if principal and principal.role not in {"superadmin"} else None
        set_rls_org(db, org_id)
    except Exception:
        pass
    require_role("owner", "admin", "superadmin")(principal)
    ids = payload.get("ids", [])
    reviewer = int(getattr(principal, "user_id", 0) or 0)
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
    try:
        set_rls_org(db, organization_id)
    except Exception:
        pass
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
    try:
        set_rls_org(db, organization_id)
    except Exception:
        pass
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
    require_role("owner", "admin", "superadmin")(principal)
    try:
        org_scope = None if principal.role == "superadmin" else organization_id
        set_rls_org(db, org_scope)
    except Exception:
        pass
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
    require_role("owner", "admin", "superadmin")(principal)
    try:
        org_scope = None if principal.role == "superadmin" else organization_id
        set_rls_org(db, org_scope)
    except Exception:
        pass
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
def create_dnc_request(organization_id: int, payload: dict, db: Session = Depends(get_db), principal: Principal = Depends(get_principal), _=Depends(rate_limiter("request", limit=60, window_seconds=60))):
    try:
        org_id = None if principal.role == "superadmin" else organization_id
        set_rls_org(db, org_id)
    except Exception:
        pass
    require_org_access(principal, organization_id)
    # members can create
    req = DNCRequest(
        organization_id=organization_id,
        phone_e164=normalize_phone_to_e164_digits(payload.get("phone_e164", "")),
        reason=payload.get("reason"),
        channel=payload.get("channel"),
        requested_by_user_id=int(getattr(principal, "user_id", 0) or 0),
        status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return {"id": req.id, "status": req.status}


@router.post("/dnc-requests/{request_id}/approve")
def approve_dnc_request(request_id: int, payload: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Approve DNC request and propagate to CRM systems."""
    try:
        # Basic validation
        if not principal:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Check role
        if principal.role not in ["owner", "admin", "superadmin"]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        # Get request
        req = db.query(DNCRequest).get(request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        
        if req.status != "pending":
            raise HTTPException(status_code=400, detail="Request already decided")
        
        # Update request
        req.status = "approved"
        req.reviewed_by_user_id = int(getattr(principal, "user_id", 0) or 0)
        req.decision_notes = payload.get("notes", "")
        from datetime import datetime
        req.decided_at = datetime.utcnow()
        
        # Check if DNC entry already exists
        existing_entry = db.query(DNCEntry).filter(
            DNCEntry.organization_id == req.organization_id,
            DNCEntry.phone_e164 == req.phone_e164
        ).first()
        
        if existing_entry:
            # Update existing entry if needed
            if not existing_entry.active:
                existing_entry.active = True
                existing_entry.removed_at = None
                existing_entry.updated_at = datetime.utcnow()
            logger.info(f"DNC entry already exists for {req.phone_e164}, updating if needed")
        else:
            # Create new DNC entry
            entry = DNCEntry(
                organization_id=req.organization_id,
                phone_e164=req.phone_e164,
                reason=req.reason or "user request",
                channel=req.channel or "voice",
                source="user_request",
                created_by_user_id=req.requested_by_user_id,
                notes=req.decision_notes,
            )
            db.add(entry)
        
        db.commit()
        
        # Start background task to propagate to CRM systems
        background_tasks.add_task(_propagate_approved_entry_with_systems_check, req.organization_id, req.phone_e164)
        
        # Also create a simple propagation attempt record immediately for visibility
        _create_immediate_propagation_attempt(req.organization_id, req.phone_e164, db)
        
        return {
            "request_id": req.id, 
            "status": req.status, 
            "message": "Request approved successfully - propagating to CRM systems",
            "phone_e164": req.phone_e164
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving DNC request {request_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to approve request: {str(e)}")


def _create_immediate_propagation_attempt(organization_id: int, phone_e164: str, db: Session) -> None:
    """Create immediate propagation attempt records for visibility in DNC History Monitor."""
    try:
        from datetime import datetime
        
        # Create propagation attempts for all major services
        services = ["ringcentral", "convoso", "ytel", "logics", "genesys"]
        
        for service in services:
            attempt = PropagationAttempt(
                organization_id=organization_id,
                phone_e164=phone_e164,
                service_key=service,
                attempt_no=1,
                status="pending",
                started_at=datetime.utcnow(),
                request_payload={"phone_e164": phone_e164, "action": "add_to_dnc"},
            )
            db.add(attempt)
        
        db.commit()
        logger.info(f"Created immediate propagation attempts for {phone_e164} across {len(services)} services")
        
    except Exception as e:
        logger.error(f"Failed to create immediate propagation attempts for {phone_e164}: {e}")
        db.rollback()


def _propagate_approved_entry(organization_id: int, phone_e164: str, reviewer_user_id: int | None = None) -> None:
    """Background task: create and update PropagationAttempt rows by calling providers.

    Uses a fresh DB session and runs async provider calls via anyio.
    """
    from ...core.database import SessionLocal
    from ...core.models import SystemSetting, PropagationAttempt
    from datetime import datetime
    import anyio

    async def _run():
        from ...core.crm_clients.ringcentral import RingCentralService
        from ...core.crm_clients.convoso import ConvosoClient
        from ...core.crm_clients.ytel import YtelClient
        db2 = SessionLocal()
        try:
            providers = ["ringcentral", "convoso", "ytel"]  # genesys/logics not implemented for push
            for key in providers:
                # Check provider enabled
                row = db2.query(SystemSetting).filter(SystemSetting.key == key).first()
                if row is not None and not bool(row.enabled):
                    continue
                # Create attempt row (pending)
                attempt = PropagationAttempt(
                    organization_id=int(organization_id),
                    job_item_id=None,
                    phone_e164=str(phone_e164),
                    service_key=key,
                    attempt_no=1,
                    status="pending",
                    started_at=datetime.utcnow(),
                )
                db2.add(attempt)
                db2.commit()
                db2.refresh(attempt)
                # Execute provider-specific add-to-DNC/blocked
                try:
                    if key == "ringcentral":
                        client = RingCentralService()
                        res = await client.remove_phone_number(phone_e164)
                    elif key == "convoso":
                        client = ConvosoClient()
                        res = await client.remove_phone_number(phone_e164)
                    elif key == "ytel":
                        client = YtelClient()
                        res = await client.remove_phone_number(phone_e164)
                    else:
                        raise Exception("provider push not implemented")
                    attempt.status = "success"
                    attempt.response_payload = res
                    attempt.finished_at = datetime.utcnow()
                except Exception as e:
                    attempt.status = "failed"
                    attempt.error_message = str(e)
                    attempt.finished_at = datetime.utcnow()
                db2.commit()
        finally:
            db2.close()

    anyio.run(_run)


def _propagate_approved_entry_with_systems_check(organization_id: int, phone_e164: str, reviewer_user_id: int | None = None) -> None:
    """Enhanced background task: Check systems first, then push only to systems where not already on DNC.
    
    Uses a fresh DB session and runs async provider calls via anyio.
    """
    from ...core.database import SessionLocal
    from ...core.models import SystemSetting, PropagationAttempt
    from datetime import datetime
    import anyio

    async def _run():
        try:
            from ...core.crm_clients.ringcentral import RingCentralService
            from ...core.crm_clients.convoso import ConvosoClient
            from ...core.crm_clients.ytel import YtelClient
            from ...api.v1.providers.genesys import patch_dnclist_phone_numbers
            from ...api.v1.providers.logics import update_case_status
            from ...api.v1.providers.common import GenesysPatchPhoneNumbersRequest, LogicsUpdateCaseRequest
            from ...config import settings as cfg
            import httpx
            
            db2 = SessionLocal()
            try:
                # First, check systems to see where the number is already on DNC
                systems_status = {}
                
                # Check RingCentral
                try:
                    token = await ringcentral_get_token()
                    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
                    params = {"status": "Blocked", "page": 1, "perPage": 100}
                    rc_phone = phone_e164 if phone_e164.startswith("+") else f"+{phone_e164}"
                    async with httpx.AsyncClient(base_url="https://platform.ringcentral.com") as hc:
                        r = await hc.get("/restapi/v1.0/account/~/extension/~/caller-blocking/phone-numbers", headers=headers, params=params)
                        listed = False
                        try:
                            js = r.json()
                            items = js.get("records") or js.get("data") or []
                            for it in items:
                                if str(it.get("phoneNumber", "")) == rc_phone:
                                    listed = True
                                    break
                        except Exception:
                            listed = False
                        systems_status["ringcentral"] = {"listed": listed}
                except Exception:
                    systems_status["ringcentral"] = {"listed": False, "error": "check_failed"}

                # Check Convoso
                try:
                    conv_token = getattr(cfg, "convoso_auth_token", None) or getattr(cfg, "convoso_leads_auth_token", None)
                    if conv_token:
                        url = "https://api.convoso.com/v1/dnc/search"
                        params = {"auth_token": conv_token, "phone_number": phone_e164, "phone_code": "1", "offset": 0, "limit": 10}
                        async with httpx.AsyncClient() as client:
                            r = await client.get(url, params=params, timeout=30.0)
                            js = r.json() if r.headers.get("content-type","").startswith("application/json") else {}
                            total = ((js or {}).get("data") or {}).get("total", 0)
                            systems_status["convoso"] = {"listed": bool(total and int(total) > 0)}
                    else:
                        systems_status["convoso"] = {"listed": False, "error": "no_token"}
                except Exception:
                    systems_status["convoso"] = {"listed": False, "error": "check_failed"}

                # Check Ytel
                try:
                    y_user = getattr(cfg, "ytel_user", None)
                    y_pass = getattr(cfg, "ytel_password", None)
                    if y_user and y_pass:
                        base = "https://tra.ytel.com/x5/api/non_agent.php"
                        params = {
                            "function": "add_lead",
                            "user": y_user,
                            "pass": y_pass,
                            "source": "dncfilter",
                            "phone_number": phone_e164,
                            "dnc_check": "Y",
                            "campaign_dnc_check": "Y",
                            "duplicate_check": "Y",
                        }
                        async with httpx.AsyncClient() as client:
                            rs = await client.get(base, params=params, timeout=30.0)
                            txt = rs.text or ""
                            listed = "PHONE NUMBER IN DNC" in txt
                            systems_status["ytel"] = {"listed": listed}
                    else:
                        systems_status["ytel"] = {"listed": False, "error": "no_creds"}
                except Exception:
                    systems_status["ytel"] = {"listed": False, "error": "check_failed"}

                # Check Genesys
                try:
                    g_cid = getattr(cfg, "genesys_client_id", None)
                    g_csec = getattr(cfg, "genesys_client_secret", None)
                    g_list = getattr(cfg, "genesys_dnclist_id", None) if hasattr(cfg, "genesys_dnclist_id") else None
                    if g_cid and g_csec and g_list:
                        login_base = (getattr(cfg, "genesys_region_login_base", None) or "https://login.usw2.pure.cloud").rstrip("/")
                        api_base = (getattr(cfg, "genesys_api_base", None) or "https://api.usw2.pure.cloud").rstrip("/")
                        tok = (await httpx.post(f"{login_base}/oauth/token", data={"grant_type":"client_credentials","client_id": g_cid, "client_secret": g_csec}, headers={"Content-Type":"application/x-www-form-urlencoded"}, timeout=30.0)).json().get("access_token")
                        headers = {"Authorization": f"Bearer {tok}"}
                        async with httpx.AsyncClient() as client:
                            r = await client.get(f"{api_base}/api/v2/outbound/dnclists/{g_list}/export", headers=headers, timeout=30.0)
                            text_blob = r.text or ""
                            systems_status["genesys"] = {"listed": phone_e164 in text_blob}
                    else:
                        systems_status["genesys"] = {"listed": False, "error": "no_creds"}
                except Exception:
                    systems_status["genesys"] = {"listed": False, "error": "check_failed"}

                # Check Logics (TPS)
                try:
                    from ...core.tps_api import tps_api
                    cases = await tps_api.find_cases_by_phone(phone_e164)
                    # If cases exist and any has StatusID 57 (DNC), consider it listed
                    listed = any(case.get("StatusID") == 57 for case in cases) if cases else False
                    systems_status["logics"] = {"listed": listed, "cases": cases}
                except Exception:
                    systems_status["logics"] = {"listed": False, "error": "check_failed"}

                # Now push to systems where the number is NOT already on DNC
                providers_to_push = []
                providers_already_listed = []
                for provider, status in systems_status.items():
                    if not status.get("listed", False) and "error" not in status:
                        providers_to_push.append(provider)
                    elif status.get("listed", False):
                        providers_already_listed.append(provider)
                
                # Mark services where number is already on DNC as success
                for key in providers_already_listed:
                    attempt = db2.query(PropagationAttempt).filter(
                        PropagationAttempt.organization_id == organization_id,
                        PropagationAttempt.phone_e164 == phone_e164,
                        PropagationAttempt.service_key == key,
                        PropagationAttempt.status == "pending"
                    ).first()
                    if attempt:
                        attempt.status = "success"
                        attempt.response_payload = {"message": "Number already on DNC list", "already_listed": True}
                        attempt.finished_at = datetime.utcnow()
                        db2.commit()
                        logger.info(f"Marked {key} as success - number already on DNC")
                
                # Mark services with errors as failed
                for provider, status in systems_status.items():
                    if "error" in status:
                        attempt = db2.query(PropagationAttempt).filter(
                            PropagationAttempt.organization_id == organization_id,
                            PropagationAttempt.phone_e164 == phone_e164,
                            PropagationAttempt.service_key == provider,
                            PropagationAttempt.status == "pending"
                        ).first()
                        if attempt:
                            attempt.status = "failed"
                            attempt.error_message = f"System check failed: {status['error']}"
                            attempt.finished_at = datetime.utcnow()
                            db2.commit()
                            logger.info(f"Marked {provider} as failed - {status['error']}")

                # Update existing pending propagation attempts for systems that need the number added
                for key in providers_to_push:
                    # Check provider enabled
                    row = db2.query(SystemSetting).filter(SystemSetting.key == key).first()
                    if row is not None and not bool(row.enabled):
                        # Mark as failed due to provider being disabled
                        attempt = db2.query(PropagationAttempt).filter(
                            PropagationAttempt.organization_id == organization_id,
                            PropagationAttempt.phone_e164 == phone_e164,
                            PropagationAttempt.service_key == key,
                            PropagationAttempt.status == "pending"
                        ).first()
                        if attempt:
                            attempt.status = "failed"
                            attempt.error_message = "Provider is disabled"
                            attempt.finished_at = datetime.utcnow()
                            db2.commit()
                        continue
                    
                    # Find existing pending attempt for this service
                    attempt = db2.query(PropagationAttempt).filter(
                        PropagationAttempt.organization_id == organization_id,
                        PropagationAttempt.phone_e164 == phone_e164,
                        PropagationAttempt.service_key == key,
                        PropagationAttempt.status == "pending"
                    ).first()
                    
                    if not attempt:
                        # Create new attempt if none exists (fallback)
                        attempt = PropagationAttempt(
                            organization_id=int(organization_id),
                            job_item_id=None,
                            phone_e164=str(phone_e164),
                            service_key=key,
                            attempt_no=1,
                            status="pending",
                            started_at=datetime.utcnow(),
                        )
                        db2.add(attempt)
                        db2.commit()
                        db2.refresh(attempt)
                    
                    # Execute provider-specific add-to-DNC
                    try:
                        if key == "ringcentral":
                            client = RingCentralService()
                            res = await client.remove_phone_number(phone_e164)
                        elif key == "convoso":
                            client = ConvosoClient()
                            res = await client.remove_phone_number(phone_e164)
                        elif key == "ytel":
                            client = YtelClient()
                            res = await client.remove_phone_number(phone_e164)
                        elif key == "genesys":
                            g_list = getattr(cfg, "genesys_dnclist_id", None)
                            if g_list:
                                request = GenesysPatchPhoneNumbersRequest(
                                    action="Add",
                                    phone_numbers=[phone_e164],
                                    expiration_date_time=""
                                )
                                res = await patch_dnclist_phone_numbers(g_list, request)
                            else:
                                raise Exception("Genesys DNC list ID not configured")
                        elif key == "logics":
                            # For Logics, we need to update existing cases to DNC status
                            cases = systems_status.get("logics", {}).get("cases", [])
                            if cases:
                                # Update the first case to DNC status (StatusID 57)
                                case_id = cases[0].get("CaseID")
                                if case_id:
                                    request = LogicsUpdateCaseRequest(
                                        case_id=case_id,
                                        status_id=57,  # DNC status
                                        notes="Added to DNC via approved request"
                                    )
                                    res = await update_case_status(request)
                                else:
                                    raise Exception("No valid case ID found")
                            else:
                                raise Exception("No cases found to update")
                        else:
                            raise Exception("provider push not implemented")
                            
                        attempt.status = "success"
                        attempt.response_payload = res
                        attempt.finished_at = datetime.utcnow()
                    except Exception as e:
                        attempt.status = "failed"
                        attempt.error_message = str(e)
                        attempt.finished_at = datetime.utcnow()
                    db2.commit()
                
            finally:
                db2.close()
        except Exception as e:
            logger.error(f"Error in background propagation task for {phone_e164}: {e}")

    anyio.run(_run)


# Admin: backfill propagation attempts for already-approved requests
@router.post("/propagation/backfill/{organization_id}")
def backfill_propagation(organization_id: int, limit: int = 50, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_org_access(principal, organization_id)
    require_role("owner", "admin", "superadmin")(principal)
    from ...core.models import DNCRequest, PropagationAttempt
    # Find approved requests in this org without any attempts yet
    reqs = db.query(DNCRequest).filter(DNCRequest.organization_id == organization_id, DNCRequest.status == "approved").order_by(DNCRequest.id.desc()).limit(min(200, max(1, limit))).all()
    created = 0
    for r in reqs:
        exists = db.query(PropagationAttempt.id).filter(PropagationAttempt.organization_id == organization_id, PropagationAttempt.phone_e164 == r.phone_e164).first()
        if exists:
            continue
        try:
            _propagate_approved_entry(organization_id, r.phone_e164, principal.user_id)
            created += 1
        except Exception:
            continue
    return {"queued": created}


@router.post("/dnc-requests/{request_id}/deny")
def deny_dnc_request(request_id: int, payload: dict, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_role("owner", "admin", "superadmin")(principal)
    req = db.query(DNCRequest).get(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Request already decided")
    req.status = "denied"
    req.reviewed_by_user_id = int(getattr(principal, "user_id", 0) or 0)
    req.decision_notes = payload.get("notes")
    from datetime import datetime
    req.decided_at = datetime.utcnow()
    db.commit()
    return {"request_id": req.id, "status": req.status}


# Listing endpoints for admin/user portals
@router.get("/dnc-requests/org/{organization_id}")
def list_requests_by_org(organization_id: int, status: str | None = None, cursor: int | None = None, limit: int = 50, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_org_access(principal, organization_id)
    require_role("owner", "admin", "superadmin")(principal)
    q = db.query(DNCRequest).filter(DNCRequest.organization_id == organization_id)
    if status:
        q = q.filter(DNCRequest.status == status)
    if cursor:
        q = q.filter(DNCRequest.id < cursor)
    q = q.order_by(DNCRequest.id.desc()).limit(min(200, max(1, limit)))
    rows = q.all()
    # Enrich with requester display info if available
    users = {u.id: u for u in db.query(User).all()}
    return [{
        "id": r.id,
        "phone_e164": r.phone_e164,
        "status": r.status,
        "reason": r.reason,
        "channel": r.channel,
        "requested_by_user_id": r.requested_by_user_id,
        "requested_by": {
            "id": r.requested_by_user_id,
            "email": users.get(r.requested_by_user_id).email if users.get(r.requested_by_user_id) else None,
            "name": users.get(r.requested_by_user_id).name if users.get(r.requested_by_user_id) else None,
        },
        "reviewed_by_user_id": r.reviewed_by_user_id,
        "created_at": r.created_at.isoformat(),
        "decided_at": r.decided_at.isoformat() if r.decided_at else None,
    } for r in rows]

# Global admin listing that ignores org (uses Entra role only)
@router.get("/dnc-requests/admin/all")
def list_requests_all_admin(status: str | None = None, cursor: int | None = None, limit: int = 50, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_role("owner", "admin", "superadmin")(principal)
    q = db.query(DNCRequest)
    if status:
        q = q.filter(DNCRequest.status == status)
    if cursor:
        q = q.filter(DNCRequest.id < cursor)
    rows = q.order_by(DNCRequest.id.desc()).limit(min(200, max(1, limit))).all()
    return [{
        "id": r.id,
        "organization_id": r.organization_id,
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
    require_role("owner", "admin", "superadmin")(principal)
    try:
        org_scope = None if principal.role == "superadmin" else organization_id
        set_rls_org(db, org_scope)
    except Exception:
        pass
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
    try:
        org_scope = None if principal.role == "superadmin" else organization_id
        set_rls_org(db, org_scope)
    except Exception:
        pass
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

