from typing import Optional
from fastapi import Header, HTTPException, status
from jose import jwt
from jose.utils import base64url_decode


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
            # Avoid signature validation for now; just read claims
            claims = jwt.get_unverified_claims(token)
            # Common Entra claim ids: oid (object id), tid (tenant id), roles / groups
            oid = claims.get("oid") or claims.get("sub")
            if oid:
                # In a full implementation, map oid→users table; here we hash-ish to int stub
                # Stable short int from last 6 hex of oid
                import re
                hexs = re.sub("[^0-9a-fA-F]", "", str(oid))[-6:]
                try:
                    user_id = int(hexs, 16)
                except Exception:
                    user_id = None
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
        except Exception:
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


