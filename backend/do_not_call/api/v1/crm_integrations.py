from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from loguru import logger

from ...core.database import get_db
from ...core.models import (
    CRMStatus, CRMStatusCreate, CRMStatusUpdate, CRMStatusResponse,
    PhoneNumber
)
from ...core.crm_clients.base import BaseCRMClient
from ...core.crm_clients.logics import LogicsClient
from ...core.crm_clients.genesys import GenesysClient
from ...core.crm_clients.ringcentral import RingCentralService
from ...core.crm_clients.convoso import ConvosoClient
from ...core.dnc_standard import BaseDNCOperationResponse, BaseDNCSearchResponse
from pydantic import BaseModel
from ...core.crm_clients.ytel import YtelClient
from ...core.tps_api import TPSApiClient
from ...core.dnc_service import dnc_service
from ...core.utils import normalize_phone_to_e164_digits
from ...core.database import get_db
from sqlalchemy.orm import Session
from ...core.models import SystemSetting
from fastapi import Response

router = APIRouter()
@router.get("/crm/statuses", tags=["Core"])
async def crm_statuses(db: Session = Depends(get_db)):
    # Placeholder: return empty list for dashboard summary until implemented
    return []
@router.get("/ringcentral/dnc/list", response_model=BaseDNCSearchResponse, tags=["RingCentral"])
async def ringcentral_list_blocked(db: Session = Depends(get_db)):
    """List blocked numbers on RingCentral (first page)."""
    from ...config import settings
    import httpx
    client = RingCentralService()
    # Ensure token/account/extension via auth_status
    st = await client.auth_status()
    if not st.get("authenticated"):
        raise HTTPException(status_code=400, detail=st.get("error") or "Auth failed")
    url = f"{client.base_url}/restapi/v1.0/account/{st['account_id']}/extension/{st['extension_id']}/caller-blocking/phone-numbers"
    headers = {"Authorization": f"Bearer {client._access_token}", "Accept": "application/json"}
    params = {"page": 1, "perPage": 100, "status": "Blocked"}
    async with httpx.AsyncClient(timeout=30) as client_http:
        try:
            resp = await client_http.get(url, headers=headers, params=params)
        except Exception as e:
            from ...core.propagation import track_provider_attempt
            await track_provider_attempt(
                db,
                organization_id=1,
                service_key="ringcentral",
                phone_e164="",
                request_context={"op": "list"},
                call=None,
            )
            raise HTTPException(status_code=502, detail=str(e))
        if resp.status_code != 200:
            from ...core.propagation import track_provider_attempt
            await track_provider_attempt(
                db,
                organization_id=1,
                service_key="ringcentral",
                phone_e164="",
                request_context={"op": "list"},
                call=None,
            )
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        data = resp.json()
        entries = [
            {
                'phone_number': r.get('phoneNumber'),
                'status': r.get('status','Blocked').lower(),
                'service_specific_id': r.get('id'),
                'date_added': None,
            }
            for r in data.get('records', [])
        ]
        # Track as success
        from ...core.propagation import track_provider_attempt
        await track_provider_attempt(
            db,
            organization_id=1,
            service_key="ringcentral",
            phone_e164="",
            request_context={"op": "list"},
            call=lambda: client.list_blocked_numbers(),
        )
        return BaseDNCSearchResponse(success=True, found=len(entries)>0, total_count=len(entries), entries=entries, service_name='ringcentral')

def _provider_enabled(db: Session, key: str) -> bool:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    return True if row is None else bool(row.enabled)


@router.post("/ringcentral/dnc/add", response_model=BaseDNCOperationResponse, tags=["RingCentral"])
async def ringcentral_block_number(phone_number: str, label: str = "API Block", db: Session = Depends(get_db)):
    if not _provider_enabled(db, "ringcentral"):
        raise HTTPException(status_code=403, detail="RingCentral integration disabled")
    """Add a phone number to RingCentral blocked list."""
    client = RingCentralService()
    from ...core.propagation import track_provider_attempt
    summary = await track_provider_attempt(
        db,
        organization_id=1,
        service_key="ringcentral",
        phone_e164=phone_number,
        request_context={"op": "add", "label": label},
        call=lambda: client.remove_phone_number(phone_number),
    )
    result = summary
    return BaseDNCOperationResponse(success=True, message='Added to blocked list', phone_number=phone_number, operation='add', service_name='ringcentral', details=result)

@router.get("/ringcentral/dnc/search/{phone_number}", response_model=BaseDNCSearchResponse, tags=["RingCentral"])
async def ringcentral_search_blocked(phone_number: str, db: Session = Depends(get_db)):
    """Search RingCentral blocked list for a phone number using JWT-auth client."""
    client = RingCentralService()
    from ...core.propagation import track_provider_attempt
    res = await client.search_blocked_number(phone_number)
    await track_provider_attempt(
        db,
        organization_id=1,
        service_key="ringcentral",
        phone_e164=phone_number,
        request_context={"op": "search"},
        call=None,
    )
    found = bool(res.get('found'))
    entry = []
    if found and res.get('record'):
        r = res['record']
        entry = [{ 'phone_number': r.get('phoneNumber'), 'status': r.get('status','Blocked').lower(), 'service_specific_id': r.get('id'), 'date_added': None }]
    return BaseDNCSearchResponse(success=True, found=found, total_count=1 if found else 0, entries=entry, service_name='ringcentral')

@router.get("/ringcentral/dnc/check/{phone_number}", tags=["RingCentral"])
async def ringcentral_check(phone_number: str):
    client = RingCentralService()
    st = await client.check_status(phone_number)
    return { 'on_dnc': st.get('status') == 'blocked', 'service': 'ringcentral' }


def get_crm_client(crm_system: str) -> BaseCRMClient:
    """Get CRM client based on system name"""
    if crm_system == "logics":
        return LogicsClient()
    elif crm_system == "genesys":
        return GenesysClient()
    elif crm_system == "ringcentral":
        return RingCentralService()
    elif crm_system == "convoso":
        return ConvosoClient()
    elif crm_system == "ytel":
        return YtelClient()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported CRM system: {crm_system}. Supported systems: logics, genesys, ringcentral, convoso, ytel"
        )


@router.post("/remove-number")
async def remove_number_from_crm(
    phone_number_id: int,
    crm_system: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Remove a phone number from a specific CRM system
    
    - **phone_number_id**: ID of the phone number to remove
    - **crm_system**: CRM system name (logics, genesys, ringcentral, convoso, ytel)
    """
    # Get phone number
    phone_number = db.query(PhoneNumber).filter(PhoneNumber.id == phone_number_id).first()
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Check if CRM status already exists
    existing_status = db.query(CRMStatus).filter(
        CRMStatus.phone_number_id == phone_number_id,
        CRMStatus.crm_system == crm_system
    ).first()
    
    if existing_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phone number already has status for {crm_system}"
        )
    
    # Create CRM status record
    crm_status = CRMStatus(
        phone_number_id=phone_number_id,
        crm_system=crm_system,
        status="pending"
    )
    db.add(crm_status)
    db.commit()
    db.refresh(crm_status)
    
    # Start background task for CRM removal
    background_tasks.add_task(
        process_crm_removal,
        crm_status.id,
        phone_number.phone_number,
        crm_system
    )
    
    logger.info(f"Started CRM removal for phone {phone_number.phone_number} in {crm_system}")
    
    return {
        "message": f"Removal request submitted for {crm_system}",
        "crm_status_id": crm_status.id,
        "status": "pending"
    }


async def process_crm_removal(crm_status_id: int, phone_number: str, crm_system: str):
    """Background task to process CRM removal"""
    from ...core.database import SessionLocal
    
    db = SessionLocal()
    try:
        # Get CRM status record
        crm_status = db.query(CRMStatus).filter(CRMStatus.id == crm_status_id).first()
        if not crm_status:
            logger.error(f"CRM status {crm_status_id} not found")
            return
        
        # Update status to processing
        crm_status.status = "processing"
        db.commit()
        
        # Get CRM client
        crm_client = get_crm_client(crm_system)
        
        # Attempt removal
        try:
            result = await crm_client.remove_phone_number(phone_number)
            
            # Update status based on result
            crm_status.status = "completed"
            crm_status.response_data = result
            crm_status.processed_at = datetime.utcnow()
            
            logger.info(f"Successfully removed {phone_number} from {crm_system}")
            
        except Exception as e:
            # Handle failure
            crm_status.status = "failed"
            crm_status.error_message = str(e)
            crm_status.retry_count += 1
            crm_status.processed_at = datetime.utcnow()
            
            logger.error(f"Failed to remove {phone_number} from {crm_system}: {e}")
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Error in CRM removal task: {e}")
    finally:
        db.close()


@router.get("/status/{phone_number}", response_model=List[CRMStatusResponse])
async def get_crm_status_by_phone(
    phone_number: str,
    db: Session = Depends(get_db)
):
    """
    Get CRM status for a specific phone number
    """
    # Find phone number record
    phone_record = db.query(PhoneNumber).filter(
        PhoneNumber.phone_number == phone_number
    ).first()
    
    if not phone_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Get all CRM statuses for this phone number
    crm_statuses = db.query(CRMStatus).filter(
        CRMStatus.phone_number_id == phone_record.id
    ).all()
    
    return [CRMStatusResponse.from_orm(status) for status in crm_statuses]


@router.get("/statuses", response_model=List[CRMStatusResponse])
async def get_all_crm_statuses(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    crm_system: Optional[str] = Query(None, description="Filter by CRM system"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """
    Get all CRM statuses with optional filtering
    """
    query = db.query(CRMStatus)
    
    # Apply filters
    if crm_system:
        query = query.filter(CRMStatus.crm_system == crm_system)
    
    if status:
        query = query.filter(CRMStatus.status == status)
    
    # Apply pagination
    crm_statuses = query.offset(skip).limit(limit).all()
    
    return [CRMStatusResponse.from_orm(status) for status in crm_statuses]


@router.post("/retry-removal")
async def retry_crm_removal(
    crm_status_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Retry a failed CRM removal
    """
    # Get CRM status record
    crm_status = db.query(CRMStatus).filter(CRMStatus.id == crm_status_id).first()
    if not crm_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CRM status not found"
        )
    
    if crm_status.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only retry failed removals"
        )
    
    # Get phone number
    phone_number = db.query(PhoneNumber).filter(
        PhoneNumber.id == crm_status.phone_number_id
    ).first()
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Reset status for retry
    crm_status.status = "pending"
    crm_status.error_message = None
    db.commit()
    
    # Start background task for retry
    background_tasks.add_task(
        process_crm_removal,
        crm_status.id,
        phone_number.phone_number,
        crm_status.crm_system
    )
    
    logger.info(f"Retrying CRM removal for {phone_number.phone_number} in {crm_status.crm_system}")
    
    return {
        "message": "Retry request submitted",
        "crm_status_id": crm_status.id,
        "status": "pending"
    }


@router.get("/stats/summary")
async def get_crm_stats(db: Session = Depends(get_db)):
    """
    Get summary statistics for CRM operations
    """
    # Get stats by CRM system
    stats = {}
    
    for crm_system in ["logics", "genesys", "ringcentral", "convoso", "ytel"]:
        total = db.query(CRMStatus).filter(CRMStatus.crm_system == crm_system).count()
        pending = db.query(CRMStatus).filter(
            CRMStatus.crm_system == crm_system,
            CRMStatus.status == "pending"
        ).count()
        processing = db.query(CRMStatus).filter(
            CRMStatus.crm_system == crm_system,
            CRMStatus.status == "processing"
        ).count()
        completed = db.query(CRMStatus).filter(
            CRMStatus.crm_system == crm_system,
            CRMStatus.status == "completed"
        ).count()
        failed = db.query(CRMStatus).filter(
            CRMStatus.crm_system == crm_system,
            CRMStatus.status == "failed"
        ).count()
        
        stats[crm_system] = {
            "total": total,
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "success_rate": (completed / total * 100) if total > 0 else 0
        }
    
    return stats


@router.get("/systems")
async def get_supported_crm_systems():
    """
    Get list of supported CRM systems
    """
    return {
        "supported_systems": [
            {
                "name": "logics",
                "display_name": "Logics",
                "description": "Logics CRM system integration"
            },
            {
                "name": "genesys",
                "display_name": "Genesys",
                "description": "Genesys contact center platform"
            },
            {
                "name": "ringcentral",
                "display_name": "Ring Central",
                "description": "Ring Central communication platform"
            },
            {
                "name": "convoso",
                "display_name": "Convoso",
                "description": "Convoso dialer platform"
            },
            {
                "name": "ytel",
                "display_name": "Ytel",
                "description": "Ytel communication platform"
            }
        ]
    }


# RingCentral helpers
@router.delete("/ringcentral/dnc/remove/{blocked_id}", response_model=BaseDNCOperationResponse, tags=["RingCentral"])
async def ringcentral_delete_blocked(blocked_id: str):
    from ...config import settings
    import httpx
    url = f"{settings.RINGCENTRAL_BASE_URL}/restapi/v1.0/account/{settings.RINGCENTRAL_ACCOUNT_ID}/extension/{settings.RINGCENTRAL_EXTENSION_ID}/caller-blocking/phone-numbers/{blocked_id}"
    headers = {"Authorization": f"Bearer {settings.RINGCENTRAL_ACCESS_TOKEN}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(url, headers=headers)
        if resp.status_code not in (200, 204):
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return BaseDNCOperationResponse(success=True, message='Removed from blocked list', phone_number='n/a', operation='remove', service_name='ringcentral', details={'blocked_id': blocked_id})


@router.get("/ringcentral/capabilities", tags=["RingCentral"])
async def ringcentral_capabilities():
    return { 'add': True, 'remove': True, 'search': True, 'list': True, 'check': True }

@router.get("/ringcentral/auth/status", tags=["RingCentral"])
async def ringcentral_auth_status():
    client = RingCentralService()
    return await client.auth_status()

# Ytel unified endpoints and capability reporting
@router.get("/ytel/dnc/search/{phone_number}", response_model=BaseDNCSearchResponse, tags=["Ytel"])
async def ytel_search_not_supported(phone_number: str):
    raise HTTPException(status_code=501, detail="Ytel does not support DNC search")

@router.delete("/ytel/dnc/remove/{phone_number}", response_model=BaseDNCOperationResponse, tags=["Ytel"])
async def ytel_remove_not_supported(phone_number: str):
    raise HTTPException(status_code=501, detail="Ytel does not support DNC removal")

@router.get("/ytel/dnc/list", response_model=BaseDNCSearchResponse, tags=["Ytel"])
async def ytel_list_not_supported():
    raise HTTPException(status_code=501, detail="Ytel does not support listing DNC entries")

@router.get("/ytel/dnc/check/{phone_number}", tags=["Ytel"])
async def ytel_check_support(phone_number: str):
    return { 'on_dnc': None, 'service': 'ytel', 'supported': False }

@router.get("/ytel/capabilities", tags=["Ytel"])
async def ytel_capabilities():
    return { 'add': True, 'remove': False, 'search': False, 'list': False, 'check': False }

# Genesys unified endpoints (placeholders)
@router.post("/genesys/dnc/add", response_model=BaseDNCOperationResponse, tags=["Genesys"])
async def genesys_add(phone_number: str):
    raise HTTPException(status_code=501, detail="Genesys DNC add not implemented yet")

@router.get("/genesys/dnc/search/{phone_number}", response_model=BaseDNCSearchResponse, tags=["Genesys"])
async def genesys_search(phone_number: str):
    raise HTTPException(status_code=501, detail="Genesys DNC search not implemented yet")

@router.delete("/genesys/dnc/remove/{phone_number}", response_model=BaseDNCOperationResponse, tags=["Genesys"])
async def genesys_remove(phone_number: str):
    raise HTTPException(status_code=501, detail="Genesys DNC removal not implemented yet")

@router.get("/genesys/dnc/check/{phone_number}", tags=["Genesys"])
async def genesys_check(phone_number: str):
    return { 'on_dnc': None, 'service': 'genesys', 'supported': False }

@router.get("/genesys/dnc/list", response_model=BaseDNCSearchResponse, tags=["Genesys"])
async def genesys_list(offset: int = 0, limit: int = 100):
    raise HTTPException(status_code=501, detail="Genesys DNC list not implemented yet")

@router.get("/genesys/capabilities", tags=["Genesys"])
async def genesys_capabilities():
    return { 'add': False, 'remove': False, 'search': False, 'list': False, 'check': False }

@router.put("/ringcentral/blocked/{blocked_id}", tags=["RingCentral"])
async def ringcentral_update_blocked(blocked_id: str, phone_number: str, status: str = "Blocked", label: str | None = None):
    from ...config import settings
    import httpx
    url = f"{settings.RINGCENTRAL_BASE_URL}/restapi/v1.0/account/{settings.RINGCENTRAL_ACCOUNT_ID}/extension/{settings.RINGCENTRAL_EXTENSION_ID}/caller-blocking/phone-numbers/{blocked_id}"
    headers = {"Authorization": f"Bearer {settings.RINGCENTRAL_ACCESS_TOKEN}", "Accept": "application/json", "Content-Type": "application/json"}
    body = {"phoneNumber": phone_number, "status": status}
    if label:
        body["label"] = label
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(url, headers=headers, json=body)
        if resp.status_code not in (200, 204):
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json() if resp.content else {"success": True}


# Convoso DNC helpers
@router.post("/convoso/dnc/add", response_model=BaseDNCOperationResponse, tags=["Convoso"])
async def convoso_dnc_insert(phone_number: str, db: Session = Depends(get_db)):
    if not _provider_enabled(db, "convoso"):
        raise HTTPException(status_code=403, detail="Convoso integration disabled")
    client = ConvosoClient()
    res = await client.remove_phone_number(phone_number)
    return BaseDNCOperationResponse(
        success=True,
        message="Added to DNC",
        phone_number=phone_number,
        operation="add",
        service_name="convoso",
        details=res,
    )

@router.get("/convoso/dnc/search/{phone_number}", response_model=BaseDNCSearchResponse, tags=["Convoso"])
async def convoso_dnc_search(
    phone_number: str,
    phone_code: int = Query(1, description="Country code, defaults to 1"),
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
):
    """Proxy Convoso DNC search to match their API semantics.

    Mirrors: GET /v1/dnc/search?auth_token=...&phone_number=...&phone_code=1&offset=0&limit=10
    """
    client = ConvosoClient()
    try:
        # Client uses configured auth_token and cookie; enforce param parity via local normalization
        raw = await client.check_status(phone_number)
        # If the client returns shape from Convoso, map to BaseDNCSearchResponse
        found = raw.get('status') == 'listed'
        entry = []
        try:
            entries = (raw.get('raw') or {}).get('data', {}).get('entries', [])
            if entries:
                e = entries[0]
                entry = [
                    {
                        'phone_number': e.get('phone_number'),
                        'status': 'blocked',
                        'date_added': None,
                        'service_specific_id': e.get('campaign_id'),
                    }
                ]
        except Exception:
            entry = []
        return BaseDNCSearchResponse(success=True, found=found, total_count=1 if found else 0, entries=entry, service_name="convoso")
    except Exception as e:
        # Surface upstream error as a 502 with message
        raise HTTPException(status_code=502, detail=str(e))

@router.delete("/convoso/dnc/remove/{phone_number}", response_model=BaseDNCOperationResponse, tags=["Convoso"])
async def convoso_dnc_delete(phone_number: str, db: Session = Depends(get_db)):
    if not _provider_enabled(db, "convoso"):
        raise HTTPException(status_code=403, detail="Convoso integration disabled")
    client = ConvosoClient()
    res = await client.delete_phone_number(phone_number)
    return BaseDNCOperationResponse(success=True, message="Removed from DNC", phone_number=phone_number, operation="remove", service_name="convoso", details=res)

@router.get("/convoso/dnc/check/{phone_number}", tags=["Convoso"])
async def convoso_dnc_check(phone_number: str):
    client = ConvosoClient()
    res = await client.check_status(phone_number)
    # Simple boolean
    return { 'success': True, 'listed': res.get('status') == 'listed' }


# Ytel modern v4 helpers
@router.post("/ytel/dnc/add", response_model=BaseDNCOperationResponse, tags=["Ytel"])
async def ytel_add_dnc(phone_number: str, db: Session = Depends(get_db)):
    if not _provider_enabled(db, "ytel"):
        raise HTTPException(status_code=403, detail="Ytel integration disabled")
    client = YtelClient()
    res = await client.remove_phone_number(phone_number)
    return BaseDNCOperationResponse(success=True, message='Added to DNC', phone_number=phone_number, operation='add', service_name='ytel', details=res)

@router.post("/ytel/dnc/bulk", tags=["Ytel"])
async def ytel_bulk_upload(file_path: str):
    """Upload a CSV file to Ytel v4 bulk DNC (server-side path)."""
    from ...config import settings
    import httpx
    headers = {"Authorization": f"Bearer {settings.YTEL_BEARER_TOKEN}"}
    url = f"{settings.YTEL_V4_BASE_URL}/dnc/bulk"
    async with httpx.AsyncClient(timeout=60) as client:
        with open(file_path, 'rb') as f:
            files = { 'file': (file_path.split('/')[-1], f, 'text/csv') }
            resp = await client.post(url, headers=headers, files=files)
            if resp.status_code not in (200, 201):
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json() if 'application/json' in resp.headers.get('content-type','') else { 'text': resp.text }


# Logics (TPS) helpers
@router.post("/logics/dnc/update-case", tags=["Logics"])
async def logics_update_case(case_id: int, status_id: int, db: Session = Depends(get_db)):
    if not _provider_enabled(db, "logics"):
        raise HTTPException(status_code=403, detail="Logics integration disabled")
    client = TPSApiClient()
    return await client.update_case_status(case_id, status_id)

@router.get("/logics/dnc/cases-by-status", tags=["Logics"])
async def logics_cases_by_status(status_id: int):
    client = TPSApiClient()
    return await client.get_cases_by_status(status_id)

@router.get("/logics/dnc/cases-by-phone", tags=["Logics"])
async def logics_cases_by_phone(phone_number: str):
    """Search TPS/Logics cases by phone number.

    Returns a concise list of cases (CaseID, CreatedDate, StatusID) for the phone.
    """
    client = TPSApiClient()
    cases = await client.find_cases_by_phone(phone_number)
    # Normalize minimal fields
    out = [
        {
            "CaseID": c.get("CaseID"),
            "CreatedDate": c.get("CreatedDate"),
            "StatusID": c.get("StatusID"),
        }
        for c in (cases or [])
    ]
    return { "success": True, "phone_number": phone_number, "count": len(out), "cases": out }


@router.get("/systems-check", tags=["Aggregate"])
async def systems_check(phone_number: str):
    """Check multiple CRM systems for DNC/blocked status for a given phone number.

    Returns a consolidated object with per-provider results.
    """
    results: dict[str, dict] = {}

    # RingCentral
    try:
        rc_client = RingCentralService()
        rc = await rc_client.check_status(phone_number)
        results["ringcentral"] = {"listed": (rc.get("status") == "blocked"), "raw": rc}
    except Exception as e:
        results["ringcentral"] = {"error": str(e)}

    # Convoso
    try:
        conv_client = ConvosoClient()
        conv = await conv_client.check_status(phone_number)
        results["convoso"] = {"listed": conv.get("status") == "listed", "raw": conv}
    except Exception as e:
        results["convoso"] = {"error": str(e)}

    # Logics (TPS) - presence if cases exist for the phone
    try:
        tps = TPSApiClient()
        cases = await tps.find_cases_by_phone(phone_number)
        results["logics"] = {"listed": len(cases) > 0, "count": len(cases), "cases": cases[:10]}
    except Exception as e:
        results["logics"] = {"error": str(e)}

    # Ytel - no read endpoint; report unknown
    results["ytel"] = {"listed": None, "note": "read not supported; add when available"}

    # Genesys - not implemented; placeholder
    results["genesys"] = {"listed": None, "note": "not implemented"}

    # Federal/National DNC check via DNC service
    try:
        dnc = await dnc_service.check_federal_dnc(phone_number)
        results["dnc"] = {
            "listed": bool(dnc.get("is_dnc")),
            "status": dnc.get("status"),
            "source": dnc.get("dnc_source"),
            "notes": dnc.get("notes"),
        }
    except Exception as e:
        results["dnc"] = {"error": str(e)}

    return {"phone_number": phone_number, "providers": results}




