from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ....core.database import get_db, set_rls_org
from ....core.auth import get_principal, Principal
from ....core.utils import normalize_phone_to_e164_digits
from ....core.propagation import track_provider_attempt
from ....core.crm_clients.genesys import GenesysClient


router = APIRouter()


class PhoneRequest(BaseModel):
    phoneNumber: str = Field(...)


@router.post("/api/genesys/auth")
async def genesys_auth():
    # Placeholder auth status endpoint; implement client credentials flow in client as needed
    return {"authenticated": True}


@router.get("/api/genesys/dnc/lists")
async def genesys_lists():
    # Placeholder; real implementation would fetch lists
    return {"lists": []}


@router.post("/api/genesys/dnc/add")
async def genesys_add(body: PhoneRequest, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    try:
        org_id = None if principal.role == "superadmin" else getattr(principal, "organization_id", None)
        set_rls_org(db, org_id)
    except Exception:
        pass
    phone = normalize_phone_to_e164_digits(body.phoneNumber)
    if not phone:
        raise HTTPException(status_code=400, detail="Invalid phoneNumber")
    client = GenesysClient()
    summary = await track_provider_attempt(
        db,
        organization_id=int(getattr(principal, "organization_id", 0) or 0),
        service_key="genesys",
        phone_e164=phone,
        request_context={"op": "add"},
        call=lambda: client.remove_phone_number(phone),
    )
    if summary.get("status") == "failed":
        raise HTTPException(status_code=502, detail=summary.get("error"))
    return {"success": True, "provider": "genesys", "phoneNumber": phone}


@router.delete("/api/genesys/dnc/delete")
async def genesys_delete(phoneNumber: str = Query(...), db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    try:
        org_id = None if principal.role == "superadmin" else getattr(principal, "organization_id", None)
        set_rls_org(db, org_id)
    except Exception:
        pass
    phone = normalize_phone_to_e164_digits(phoneNumber)
    if not phone:
        raise HTTPException(status_code=400, detail="Invalid phoneNumber")
    # Placeholder: no real delete yet
    await track_provider_attempt(
        db,
        organization_id=int(getattr(principal, "organization_id", 0) or 0),
        service_key="genesys",
        phone_e164=phone,
        request_context={"op": "delete"},
        call=None,
    )
    return {"success": True}


