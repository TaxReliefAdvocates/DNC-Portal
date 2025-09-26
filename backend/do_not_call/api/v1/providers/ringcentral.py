from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any
from loguru import logger
import base64

from .common import (
    AddToDNCRequest,
    SearchDNCRequest,
    SearchMultipleDNCRequest,
    ListAllDNCRequest,
    DeleteFromDNCRequest,
    UploadDNCListRequest,
    SearchByPhoneRequest,
    DNCOperationResponse,
    ComingSoonResponse,
)
from do_not_call.config import settings
from .http_client import HttpClient

router = APIRouter()


async def ringcentral_get_token(assertion: Optional[str] = None, client_basic_b64: Optional[str] = None) -> str:
    # Prefer explicit assertion, then settings.ringcentral_jwt_assertion, then legacy settings.ringcentral_jwt
    jwt_assertion = assertion or settings.ringcentral_jwt_assertion or getattr(settings, 'ringcentral_jwt', None)
    
    if not jwt_assertion:
        raise HTTPException(status_code=400, detail="RingCentral JWT assertion required.")
    headers: Dict[str, str] = {"Content-Type": "application/x-www-form-urlencoded"}
    basic_b64 = client_basic_b64 or settings.ringcentral_basic_b64
    if not basic_b64 and settings.ringcentral_client_id and settings.ringcentral_client_secret:
        creds = f"{settings.ringcentral_client_id}:{settings.ringcentral_client_secret}".encode()
        basic_b64 = base64.b64encode(creds).decode()
    if basic_b64:
        headers["Authorization"] = f"Basic {basic_b64}"
    async with HttpClient(base_url="https://platform.ringcentral.com") as http:
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": jwt_assertion,
        }
        resp = await http.post("/restapi/oauth/token", data=data, headers=headers)
        json = resp.json()
        access_token = json.get("access_token")
        if not access_token:
            logger.error(f"RingCentral token response missing access_token: {json}")
            raise HTTPException(status_code=500, detail="Failed to obtain RingCentral access token")
        return access_token


@router.post("/auth", response_model=DNCOperationResponse)
async def auth(assertion: Optional[str] = None, client_basic_b64: Optional[str] = None):
    token = await ringcentral_get_token(assertion, client_basic_b64)
    return DNCOperationResponse(success=True, message="Obtained RingCentral token", data={"access_token": token})


@router.post("/add-dnc", response_model=DNCOperationResponse)
async def add_to_dnc(request: AddToDNCRequest, bearer_token: Optional[str] = None, assertion: Optional[str] = None):
    token = bearer_token or await ringcentral_get_token(assertion)
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json", "content-type": "application/json"}
    payload = {"phoneNumber": f"+{request.phone_code or ''}{request.phone_number}", "status": "Blocked"}
    async with HttpClient(base_url="https://platform.ringcentral.com") as http:
        resp = await http.post("/restapi/v1.0/account/~/extension/~/caller-blocking/phone-numbers", json=payload, headers=headers)
        return DNCOperationResponse(success=True, message="Added to DNC (RingCentral)", data=resp.json())


@router.post("/delete-dnc", response_model=DNCOperationResponse)
async def delete_from_dnc(request: DeleteFromDNCRequest, bearer_token: Optional[str] = None, assertion: Optional[str] = None):
    if not request.resource_id:
        raise HTTPException(status_code=400, detail="resource_id is required for RingCentral delete")
    token = bearer_token or await ringcentral_get_token(assertion)
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
    url = f"/restapi/v1.0/account/~/extension/~/caller-blocking/phone-numbers/{request.resource_id}"
    async with HttpClient(base_url="https://platform.ringcentral.com") as http:
        resp = await http.delete(url, headers=headers)
        return DNCOperationResponse(success=True, message="Deleted from DNC (RingCentral)", data={"status_code": resp.status_code})


@router.post("/search-dnc", response_model=DNCOperationResponse)
async def search_dnc(request: SearchDNCRequest, bearer_token: Optional[str] = None, assertion: Optional[str] = None):
    """
    Search for a specific phone number in RingCentral DNC list.
    Returns true/false if the number is found on the DNC list.
    """
    token = bearer_token or await ringcentral_get_token(assertion)
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
    
    # Get all DNC entries to search through
    params = {"page": 1, "perPage": 1000}  # Get more results to search through
    async with HttpClient(base_url="https://platform.ringcentral.com") as http:
        resp = await http.get("/restapi/v1.0/account/~/extension/~/caller-blocking/phone-numbers", headers=headers, params=params)
        data = resp.json()
        
        # Search for the specific phone number in the results
        is_on_dnc = False
        target_number = request.phone_number
        
        try:
            records = data.get("records", [])
            for record in records:
                phone_number = record.get("phoneNumber", "")
                # Normalize both numbers for comparison (remove +, spaces, dashes, etc.)
                normalized_api_number = phone_number.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
                normalized_target = target_number.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
                
                if normalized_api_number == normalized_target:
                    is_on_dnc = True
                    break
        except Exception as e:
            logger.error(f"Error parsing RingCentral response: {e}")
        
        return DNCOperationResponse(
            success=True, 
            message=f"Number {target_number} {'IS' if is_on_dnc else 'IS NOT'} on RingCentral DNC list", 
            data={
                "phone_number": target_number,
                "is_on_dnc": is_on_dnc,
                "raw_response": data
            }
        )


@router.post("/search-multiple-dnc", response_model=DNCOperationResponse)
async def search_multiple_dnc(request: SearchMultipleDNCRequest, bearer_token: Optional[str] = None, assertion: Optional[str] = None):
    """
    Search for multiple phone numbers in RingCentral DNC list.
    Returns results for each number indicating if it's found on the DNC list.
    """
    token = bearer_token or await ringcentral_get_token(assertion)
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
    
    # Get all DNC entries to search through
    params = {"page": 1, "perPage": 1000}
    async with HttpClient(base_url="https://platform.ringcentral.com") as http:
        resp = await http.get("/restapi/v1.0/account/~/extension/~/caller-blocking/phone-numbers", headers=headers, params=params)
        data = resp.json()
        
        # Search for each phone number in the results
        results = {}
        dnc_numbers = set()
        
        try:
            records = data.get("records", [])
            for record in records:
                phone_number = record.get("phoneNumber", "")
                # Normalize the API number
                normalized_api_number = phone_number.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
                dnc_numbers.add(normalized_api_number)
            
            # Check each target number
            for target_number in request.phone_numbers:
                normalized_target = target_number.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
                results[target_number] = {
                    "is_on_dnc": normalized_target in dnc_numbers,
                    "phone_number": target_number
                }
                
        except Exception as e:
            logger.error(f"Error parsing RingCentral response: {e}")
            # Return error for all numbers
            for target_number in request.phone_numbers:
                results[target_number] = {
                    "is_on_dnc": False,
                    "phone_number": target_number,
                    "error": str(e)
                }
        
        return DNCOperationResponse(
            success=True, 
            message=f"Checked {len(request.phone_numbers)} numbers against RingCentral DNC list", 
            data={
                "results": results,
                "total_checked": len(request.phone_numbers),
                "raw_response": data
            }
        )


@router.post("/list-all-dnc", response_model=DNCOperationResponse)
async def list_all_dnc(request: ListAllDNCRequest, bearer_token: Optional[str] = None, assertion: Optional[str] = None):
    token = bearer_token or await ringcentral_get_token(assertion)
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
    params = {"page": request.page, "perPage": request.per_page}
    if request.status:
        params["status"] = request.status
    async with HttpClient(base_url="https://platform.ringcentral.com") as http:
        resp = await http.get("/restapi/v1.0/account/~/extension/~/caller-blocking/phone-numbers", headers=headers, params=params)
        data = resp.json()
        return DNCOperationResponse(success=True, message="Listed DNC entries (RingCentral)", data=data)


@router.get("/blocked/{resource_id}", response_model=DNCOperationResponse)
async def get_blocked_entry(resource_id: str, bearer_token: Optional[str] = None, assertion: Optional[str] = None):
    token = bearer_token or await ringcentral_get_token(assertion)
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
    url = f"/restapi/v1.0/account/~/extension/~/caller-blocking/phone-numbers/{resource_id}"
    async with HttpClient(base_url="https://platform.ringcentral.com") as http:
        resp = await http.get(url, headers=headers)
        return DNCOperationResponse(success=True, message="Fetched blocked entry (RingCentral)", data=resp.json())


@router.post("/upload-dnc-list-coming-soon", tags=["Coming Soon"], response_model=ComingSoonResponse)
async def upload_dnc_placeholder(_: UploadDNCListRequest):
    return ComingSoonResponse()


@router.post("/search-by-phone-coming-soon", tags=["Coming Soon"], response_model=ComingSoonResponse)
async def search_by_phone_placeholder(_: SearchByPhoneRequest):
    return ComingSoonResponse()


