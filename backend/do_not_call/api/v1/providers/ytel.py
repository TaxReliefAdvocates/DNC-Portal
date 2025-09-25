from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional

from ....core.database import get_db, set_rls_org
from ....core.auth import get_principal, Principal
from ....core.utils import normalize_phone_to_e164_digits
from ....core.propagation import track_provider_attempt
from ....core.crm_clients.ytel import YtelClient


router = APIRouter()


class PhoneRequest(BaseModel):
    phoneNumber: str | None = Field(None, description="Phone number in E.164 format or US digits")
    phone_number: str | None = Field(None, description="Alternate Field: phone_number")

def _resolve_phone_inputs(phoneNumber: str | None = None, phone_number: str | None = None, body: PhoneRequest | None = None) -> str:
    return (phoneNumber or phone_number or (body.phoneNumber if body else None) or (body.phone_number if body else None) or "")


@router.post("/ytel/dnc/add")
async def ytel_add(
    phoneNumber: str | None = Query(None, alias="phoneNumber"),
    phone_number: str | None = Query(None, alias="phone_number"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
):
    try:
        org_id = None if principal.role == "superadmin" else getattr(principal, "organization_id", None)
        set_rls_org(db, org_id)
    except Exception:
        pass
    phone = normalize_phone_to_e164_digits(_resolve_phone_inputs(phoneNumber, phone_number))
    if not phone:
        raise HTTPException(status_code=400, detail="Missing or invalid query parameter: phone_number or phoneNumber")
    client = YtelClient()
    summary = await track_provider_attempt(
        db,
        organization_id=int(getattr(principal, "organization_id", 0) or 0),
        service_key="ytel",
        phone_e164=phone,
        request_context={"op": "add"},
        call=lambda: client.remove_phone_number(phone),
    )
    if summary.get("status") == "failed":
        raise HTTPException(status_code=502, detail=summary.get("error"))
    return {"success": True, "provider": "ytel", "phoneNumber": phone}


@router.post("/ytel/dnc/search")
async def ytel_search(
    phoneNumber: str | None = Query(None, alias="phoneNumber"),
    phone_number: str | None = Query(None, alias="phone_number"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
):
    try:
        org_id = None if principal.role == "superadmin" else getattr(principal, "organization_id", None)
        set_rls_org(db, org_id)
    except Exception:
        pass
    phone = normalize_phone_to_e164_digits(_resolve_phone_inputs(phoneNumber, phone_number))
    if not phone:
        raise HTTPException(status_code=400, detail="Missing or invalid query parameter: phone_number or phoneNumber")
    client = YtelClient()
    res = await client.check_status(phone)
    await track_provider_attempt(
        db,
        organization_id=int(getattr(principal, "organization_id", 0) or 0),
        service_key="ytel",
        phone_e164=phone,
        request_context={"op": "search"},
        call=None,
    )
    return res


@router.post("/ytel/dnc/remove")
async def ytel_remove(
    phoneNumber: str | None = Query(None, alias="phoneNumber"),
    phone_number: str | None = Query(None, alias="phone_number"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
):
    try:
        org_id = None if principal.role == "superadmin" else getattr(principal, "organization_id", None)
        set_rls_org(db, org_id)
    except Exception:
        pass
    phone = normalize_phone_to_e164_digits(_resolve_phone_inputs(phoneNumber, phone_number))
    if not phone:
        raise HTTPException(status_code=400, detail="Missing or invalid query parameter: phone_number or phoneNumber")
    client = YtelClient()
    summary = await track_provider_attempt(
        db,
        organization_id=int(getattr(principal, "organization_id", 0) or 0),
        service_key="ytel",
        phone_e164=phone,
        request_context={"op": "remove"},
        call=lambda: client.remove_phone_number(phone),
    )
    if summary.get("status") == "failed":
        raise HTTPException(status_code=502, detail=summary.get("error"))
    return {"success": True, "provider": "ytel", "phoneNumber": phone}


