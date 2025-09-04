from typing import Optional
from fastapi import Header, HTTPException, status


class Principal:
    def __init__(self, user_id: Optional[int], organization_id: Optional[int], role: str = "member"):
        self.user_id = user_id
        self.organization_id = organization_id
        self.role = role


async def get_principal(
    x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_role: Optional[str] = Header(default=None, alias="X-Role"),
) -> Principal:
    """Stub mapping for Entra ID claims → principal.
    Frontend/gateway should map Entra claims into headers X-Org-Id, X-User-Id, X-Role.
    """
    try:
        org_id = int(x_org_id) if x_org_id else None
        user_id = int(x_user_id) if x_user_id else None
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid principal headers")
    role = (x_role or "member").lower()
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


