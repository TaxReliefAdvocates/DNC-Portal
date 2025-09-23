from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ....core.database import get_db, set_rls_org
from ....core.auth import get_principal, Principal
from ....core.utils import normalize_phone_to_e164_digits
from ....core.propagation import track_provider_attempt
from ....core.tps_api import TPSApiClient


router = APIRouter()


class PhoneRequest(BaseModel):
    phoneNumber: str = Field(...)


@router.post("/api/logics/dnc/add")
async def logics_add(body: PhoneRequest, statusId: int = Query(0), db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    try:
        org_id = None if principal.role == "superadmin" else getattr(principal, "organization_id", None)
        set_rls_org(db, org_id)
    except Exception:
        pass
    phone = normalize_phone_to_e164_digits(body.phoneNumber)
    if not phone:
        raise HTTPException(status_code=400, detail="Invalid phoneNumber")
    client = TPSApiClient()
    # Resolve cases and update first found as DNC
    cases = await client.find_cases_by_phone(phone)
    if not cases:
        raise HTTPException(status_code=404, detail="No case found for phone")
    case_id = cases[0].get("CaseID")
    summary = await track_provider_attempt(
        db,
        organization_id=int(getattr(principal, "organization_id", 0) or 0),
        service_key="logics",
        phone_e164=phone,
        request_context={"op": "add", "case_id": case_id, "status_id": statusId},
        call=lambda: client.update_case_status(int(case_id), int(statusId or 0)),
    )
    if summary.get("status") == "failed":
        raise HTTPException(status_code=502, detail=summary.get("error"))
    return {"success": True, "provider": "logics", "phoneNumber": phone, "caseId": case_id}


@router.get("/api/logics/dnc/search")
async def logics_search(phoneNumber: str = Query(...)):
    client = TPSApiClient()
    cases = await client.find_cases_by_phone(phoneNumber)
    return {"success": True, "phoneNumber": phoneNumber, "count": len(cases), "cases": cases}


