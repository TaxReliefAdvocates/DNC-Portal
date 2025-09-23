from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ....core.database import get_db, set_rls_org
from ....core.auth import get_principal, Principal
from ....core.utils import normalize_phone_to_e164_digits
from ....core.propagation import track_provider_attempt
from ....core.crm_clients.ringcentral import RingCentralService


router = APIRouter()


class PhoneRequest(BaseModel):
    phoneNumber: str = Field(...)


@router.post("/ringcentral/auth")
async def ringcentral_auth():
    client = RingCentralService()
    st = await client.auth_status()
    if not st.get("authenticated"):
        raise HTTPException(status_code=400, detail=st.get("error") or "Auth failed")
    return st


@router.post("/ringcentral/dnc/add")
async def ringcentral_add(body: PhoneRequest, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    try:
        org_id = None if principal.role == "superadmin" else getattr(principal, "organization_id", None)
        set_rls_org(db, org_id)
    except Exception:
        pass
    phone = normalize_phone_to_e164_digits(body.phoneNumber)
    if not phone:
        raise HTTPException(status_code=400, detail="Invalid phoneNumber")
    client = RingCentralService()
    summary = await track_provider_attempt(
        db,
        organization_id=int(getattr(principal, "organization_id", 0) or 0),
        service_key="ringcentral",
        phone_e164=phone,
        request_context={"op": "add"},
        call=lambda: client.remove_phone_number(phone),
    )
    if summary.get("status") == "failed":
        raise HTTPException(status_code=502, detail=summary.get("error"))
    return {"success": True, "provider": "ringcentral", "phoneNumber": phone}


@router.get("/ringcentral/dnc/list")
async def ringcentral_list():
    client = RingCentralService()
    try:
        return await client.list_blocked_numbers()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/ringcentral/dnc/search")
async def ringcentral_search(phoneNumber: str = Query(...)):
    client = RingCentralService()
    return await client.search_blocked_number(phoneNumber)


@router.delete("/ringcentral/dnc/delete")
async def ringcentral_delete(phoneNumber: str = Query(...)):
    client = RingCentralService()
    ok = await client.remove_blocked_number(phoneNumber)
    if not ok:
        raise HTTPException(status_code=404, detail="Phone number not found")
    return {"success": True}


