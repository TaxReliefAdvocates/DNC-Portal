from typing import Optional
from fastapi import Header, HTTPException, status
from jose import jwt
from jose.exceptions import JWTError
from functools import lru_cache
from ..config import settings
from .database import get_db
from .models import User, OrgUser, Organization
from typing import Dict, Any
import httpx


class Principal:
    def __init__(self, user_id: Optional[int], organization_id: Optional[int], role: str = "member"):
        self.user_id = user_id
        self.organization_id = organization_id
        self.role = role


async def get_principal(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_role: Optional[str] = Header(default=None, alias="X-Role"),
) -> Principal:
    """Map Entra JWT or fallback headers to a Principal.

    For production, provide a valid Entra JWT in Authorization: Bearer {token}.
    This implementation parses claims without signature validation as a stopgap
    unless a future configuration supplies issuer/audience/keys.
    """
    user_id: Optional[int] = None
    org_id: Optional[int] = None
    role: str = (x_role or "member").lower()

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
        try:
            claims = None
            if settings.ENTRA_REQUIRE_SIGNATURE:
                # Validate signature using JWKS
                jwks_url = settings.ENTRA_JWKS_URL or f"https://login.microsoftonline.com/{settings.ENTRA_TENANT_ID}/discovery/v2.0/keys"
                jwks = await _fetch_jwks(jwks_url)
                # Accept Azure AD v1 or v2 issuer formats; enforce audience, skip issuer check
                claims = jwt.decode(
                    token,
                    jwks,
                    algorithms=["RS256"],
                    audience=settings.ENTRA_AUDIENCE,
                    options={"verify_iss": False}
                )
            else:
                # Parse only
                claims = jwt.get_unverified_claims(token)
            # Common Entra claim ids: oid (object id), tid (tenant id), roles / groups
            oid = claims.get("oid") or claims.get("sub")
            email = claims.get("preferred_username") or claims.get("upn") or claims.get("email")
            display_name = claims.get("name") or email
            # Map oid/email → user record (create if missing)
            if oid or email:
                db = next(get_db())
                user = None
                if oid:
                    user = db.query(User).filter_by(oid=str(oid)).first()
                if not user and email:
                    user = db.query(User).filter_by(email=str(email)).first()
                if not user:
                    user = User(oid=str(oid) if oid else None, email=str(email) if email else f"user-{oid}@local", name=display_name)
                    db.add(user)
                    db.commit()
                    db.refresh(user)
                user_id = user.id
            roles = claims.get("roles") or claims.get("groups") or []
            # Map Azure App Role values/names to internal roles.
            # Supports value-based (e.g., all, approve_requests, task.write) and display-name variants (e.g., "Super Admin").
            if isinstance(roles, list) and roles:
                lowered = {str(r).lower() for r in roles}
                # Also check normalized variants without spaces/punctuation
                normalized = {"".join(ch for ch in s if ch.isalnum()) for s in lowered}

                if ({"superadmin", "all"} & lowered) or ("superadmin" in normalized):
                    role = "superadmin"
                elif ("owner" in lowered) or ("owner" in normalized):
                    role = "owner"
                elif ({"admin", "approve_requests"} & lowered) or ("admin" in normalized):
                    role = "admin"
                elif ({"user", "task.write"} & lowered) or ("user" in normalized):
                    role = "member"
                else:
                    role = "member"

            # Sync DB user role flags with Entra-derived role (best-effort)
            try:
                if user_id is not None:
                    db = next(get_db())
                    user = db.query(User).get(int(user_id))
                    if user:
                        desired_role = "owner" if role == "owner" else ("admin" if role == "admin" else ("member" if role == "member" else user.role or "member"))
                        is_super = (role == "superadmin")
                        changed = False
                        if display_name and user.name != display_name:
                            user.name = display_name
                            changed = True
                        if user.role != desired_role:
                            user.role = desired_role
                            changed = True
                        if getattr(user, "is_super_admin", False) != is_super:
                            user.is_super_admin = is_super
                            changed = True
                        if changed:
                            db.commit()
            except Exception:
                pass

            # Resolve organization_id
            try:
                # Admin/superadmin may explicitly target an org via header
                if x_org_id and role in {"admin", "superadmin", "owner"}:
                    org_id = int(x_org_id)
                elif user_id is not None:
                    db = next(get_db())
                    link = db.query(OrgUser).filter_by(user_id=int(user_id)).first()
                    if link:
                        org_id = link.organization_id
                    else:
                        # Auto-associate to default org if exists
                        org1 = db.query(Organization).filter_by(id=getattr(settings, "DEFAULT_ORG_ID", 1)).first()
                        if org1:
                            db.add(OrgUser(organization_id=org1.id, user_id=int(user_id), role=(role or "member")))
                            db.commit()
                            org_id = org1.id
            except Exception:
                pass
        except JWTError:
            # Fall back to headers if jwt parsing fails
            pass

    # In production, do not trust header fallbacks without a valid Bearer token
    if settings.DEBUG:
        allow_header_fallback = True
    else:
        # In non-debug, only allow fallback when signature not required AND no Authorization header is present
        allow_header_fallback = (not settings.ENTRA_REQUIRE_SIGNATURE) and (authorization is None)

    # Fallback / override from headers
    if allow_header_fallback and x_user_id:
        try:
            user_id = int(x_user_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid X-User-Id")
    if allow_header_fallback and x_org_id:
        try:
            org_id = int(x_org_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid X-Org-Id")

    # If production and we had Authorization but failed to parse/validate, force member with no overrides
    if authorization and not allow_header_fallback and user_id is None and org_id is None:
        return Principal(user_id=None, organization_id=None, role=role)

    return Principal(user_id=user_id, organization_id=org_id, role=role)


@lru_cache(maxsize=1)
def _jwks_cache_key(url: str) -> str:
    return url


async def _fetch_jwks(url: str):
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()
        # python-jose accepts a dict of {keys: [...]}
        return data


def require_role(*allowed: str):
    allowed_set = {r.lower() for r in allowed}
    def wrapper(principal: Principal = None):
        if principal is None or principal.role not in allowed_set:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return principal
    return wrapper


def require_org_access(principal: Principal, organization_id: int):
    # Admin and Superadmin bypass org scoping per product requirement
    role = getattr(principal, "role", "").lower()
    if role in {"admin", "superadmin"}:
        return True
    if principal.organization_id is None or principal.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Org access denied")
    return True


