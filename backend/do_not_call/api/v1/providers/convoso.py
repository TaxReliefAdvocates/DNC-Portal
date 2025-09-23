from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ....core.database import get_db, set_rls_org
from ....core.auth import get_principal, Principal
from ....core.utils import normalize_phone_to_e164_digits
from ....core.propagation import track_provider_attempt
from ....core.crm_clients.convoso import ConvosoClient


router = APIRouter()


class PhoneRequest(BaseModel):
    phoneNumber: str = Field(..., description="Phone number in E.164 format or US digits")


@router.post("/convoso/dnc/add")
async def convoso_add(body: PhoneRequest, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    try:
        org_id = None if principal.role == "superadmin" else getattr(principal, "organization_id", None)
        set_rls_org(db, org_id)
    except Exception:
        pass
    phone = normalize_phone_to_e164_digits(body.phoneNumber)
    if not phone:
        raise HTTPException(status_code=400, detail="Invalid phoneNumber")
    client = ConvosoClient()
    summary = await track_provider_attempt(
        db,
        organization_id=int(getattr(principal, "organization_id", 0) or 0),
        service_key="convoso",
        phone_e164=phone,
        request_context={"op": "add"},
        call=lambda: client.remove_phone_number(phone),
    )
    if summary.get("status") == "failed":
        raise HTTPException(status_code=502, detail=summary.get("error"))
    return {"success": True, "provider": "convoso", "phoneNumber": phone}


@router.get("/convoso/dnc/search")
async def convoso_search(phoneNumber: str = Query(...), db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    try:
        org_id = None if principal.role == "superadmin" else getattr(principal, "organization_id", None)
        set_rls_org(db, org_id)
    except Exception:
        pass
    phone = normalize_phone_to_e164_digits(phoneNumber)
    if not phone:
        raise HTTPException(status_code=400, detail="Invalid phoneNumber")
    client = ConvosoClient()
    res = await client.check_status(phone)
    await track_provider_attempt(
        db,
        organization_id=int(getattr(principal, "organization_id", 0) or 0),
        service_key="convoso",
        phone_e164=phone,
        request_context={"op": "search"},
        call=None,
    )
    return res


@router.delete("/convoso/dnc/delete")
async def convoso_delete(phoneNumber: str = Query(...), db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    try:
        org_id = None if principal.role == "superadmin" else getattr(principal, "organization_id", None)
        set_rls_org(db, org_id)
    except Exception:
        pass
    phone = normalize_phone_to_e164_digits(phoneNumber)
    if not phone:
        raise HTTPException(status_code=400, detail="Invalid phoneNumber")
    client = ConvosoClient()
    summary = await track_provider_attempt(
        db,
        organization_id=int(getattr(principal, "organization_id", 0) or 0),
        service_key="convoso",
        phone_e164=phone,
        request_context={"op": "delete"},
        call=lambda: client.delete_phone_number(phone),
    )
    if summary.get("status") == "failed":
        raise HTTPException(status_code=502, detail=summary.get("error"))
    return {"success": True, "provider": "convoso", "phoneNumber": phone}


@router.get("/convoso/leads/search")
async def convoso_leads_search(phoneNumber: str = Query(...), db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    try:
        org_id = None if principal.role == "superadmin" else getattr(principal, "organization_id", None)
        set_rls_org(db, org_id)
    except Exception:
        pass
    phone = normalize_phone_to_e164_digits(phoneNumber)
    if not phone:
        raise HTTPException(status_code=400, detail="Invalid phoneNumber")
    client = ConvosoClient()
    res = await client.search_leads_by_phone(phone)
    await track_provider_attempt(
        db,
        organization_id=int(getattr(principal, "organization_id", 0) or 0),
        service_key="convoso",
        phone_e164=phone,
        request_context={"op": "leads_search"},
        call=None,
    )
    return res


