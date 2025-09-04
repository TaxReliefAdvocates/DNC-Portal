from typing import Optional
from fastapi import Header, HTTPException, status
from jose import jwt
from jose.exceptions import JWTError
import httpx
from functools import lru_cache
from ..config import settings
from .database import get_db
from .models import User, OrgUser, Organization


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
                claims = jwt.decode(
                    token,
                    jwks,
                    algorithms=["RS256"],
                    audience=settings.ENTRA_AUDIENCE,
                    issuer=settings.ENTRA_ISSUER or f"https://login.microsoftonline.com/{settings.ENTRA_TENANT_ID}/v2.0"
                )
            else:
                # Parse only
                claims = jwt.get_unverified_claims(token)
            # Common Entra claim ids: oid (object id), tid (tenant id), roles / groups
            oid = claims.get("oid") or claims.get("sub")
            email = claims.get("preferred_username") or claims.get("upn") or claims.get("email")
            # Map oid/email → user record (create if missing)
            if oid or email:
                db = next(get_db())
                user = None
                if oid:
                    user = db.query(User).filter_by(oid=str(oid)).first()
                if not user and email:
                    user = db.query(User).filter_by(email=str(email)).first()
                if not user:
                    user = User(oid=str(oid) if oid else None, email=str(email) if email else f"user-{oid}@local", name=email)
                    db.add(user)
                    db.commit()
                    db.refresh(user)
                user_id = user.id
            roles = claims.get("roles") or claims.get("groups") or []
            if isinstance(roles, list) and roles:
                # Prefer owner/admin if present
                lowered = {str(r).lower() for r in roles}
                if "owner" in lowered:
                    role = "owner"
                elif "admin" in lowered:
                    role = "admin"
                else:
                    role = "member"
        except JWTError:
            # Fall back to headers if jwt parsing fails
            pass

    # Fallback / override from headers
    if x_user_id:
        try:
            user_id = int(x_user_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid X-User-Id")
    if x_org_id:
        try:
            org_id = int(x_org_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid X-Org-Id")

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
    if principal.organization_id is None or principal.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Org access denied")
    return True


