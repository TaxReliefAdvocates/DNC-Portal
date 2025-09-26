from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any
from loguru import logger

from .common import (
	AddToDNCRequest,
	SearchDNCRequest,
	ListAllDNCRequest,
	DeleteFromDNCRequest,
	UploadDNCListRequest,
	SearchByPhoneRequest,
	DNCOperationResponse,
	ComingSoonResponse,
)
from do_not_call.config import settings
from .http_client import HttpClient
from pydantic import BaseModel

router = APIRouter()


async def genesys_get_token(client_id: Optional[str] = None, client_secret: Optional[str] = None) -> str:
	cid = client_id or settings.genesys_client_id
	sec = client_secret or settings.genesys_client_secret
	if not cid or not sec:
		raise HTTPException(status_code=400, detail="Genesys client_id/client_secret required")
	login_base = settings.genesys_region_login_base.rstrip("/")
	async with HttpClient(base_url=login_base) as http:
		data = {"grant_type": "client_credentials", "client_id": cid, "client_secret": sec}
		resp = await http.post("/oauth/token", data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
		json = resp.json()
		token = json.get("access_token")
		if not token:
			raise HTTPException(status_code=500, detail="Failed to obtain Genesys access token")
		return token


@router.post("/auth", response_model=DNCOperationResponse)
async def auth(client_id: Optional[str] = None, client_secret: Optional[str] = None):
	token = await genesys_get_token(client_id, client_secret)
	return DNCOperationResponse(success=True, message="Obtained Genesys token", data={"access_token": token})


@router.post("/list-all-dnc", response_model=DNCOperationResponse)
async def list_all_dnc(request: ListAllDNCRequest, bearer_token: Optional[str] = None, client_id: Optional[str] = None, client_secret: Optional[str] = None):
	token = bearer_token or await genesys_get_token(client_id, client_secret)
	headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
	api_base = settings.genesys_api_base.rstrip("/")
	async with HttpClient(base_url=api_base) as http:
		resp = await http.get("/api/v2/outbound/dnclists", headers=headers)
		return DNCOperationResponse(success=True, message="Listed DNC lists (Genesys)", data=resp.json())


class GenesysPatchPhoneNumbersRequest(BaseModel):
	action: str  # "Add" | "Remove"
	phone_numbers: List[str]
	expiration_date_time: Optional[str] = None  # ISO8601 or empty string
	bearer_token: Optional[str] = None
	client_id: Optional[str] = None
	client_secret: Optional[str] = None


@router.patch("/dnclists/{list_id}/phonenumbers", response_model=DNCOperationResponse)
async def patch_dnclist_phone_numbers(list_id: str, req: GenesysPatchPhoneNumbersRequest):
	# Acquire token
	token = req.bearer_token or (await genesys_get_token(req.client_id, req.client_secret))
	api_base = settings.genesys_api_base.rstrip("/")
	headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
	payload: Dict[str, Any] = {
		"action": req.action,
		"phoneNumbers": req.phone_numbers,
	}
	# Genesys accepts empty string or ISO timestamp; pass only if provided
	if req.expiration_date_time is not None:
		payload["expirationDateTime"] = req.expiration_date_time
	url = f"/api/v2/outbound/dnclists/{list_id}/phonenumbers"
	async with HttpClient(base_url=api_base) as http:
		resp = await http.patch(url, json=payload, headers=headers)
		data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw": resp.text}
		return DNCOperationResponse(success=True, message="Patched DNC list phone numbers (Genesys)", data=data)


class GenesysExportCheckRequest(BaseModel):
	phone_numbers: List[str]
	bearer_token: Optional[str] = None
	client_id: Optional[str] = None
	client_secret: Optional[str] = None


@router.post("/dnclists/{list_id}/check", response_model=DNCOperationResponse)
async def check_numbers_in_dnclist(list_id: str, req: GenesysExportCheckRequest):
	# Acquire token
	token = req.bearer_token or (await genesys_get_token(req.client_id, req.client_secret))
	api_base = settings.genesys_api_base.rstrip("/")
	headers = {"Authorization": f"Bearer {token}"}
	url = f"/api/v2/outbound/dnclists/{list_id}/export"
	async with HttpClient(base_url=api_base) as http:
		resp = await http.get(url, headers=headers)
		content_type = resp.headers.get("content-type", "").lower()
		result: Dict[str, Any] = {}
		text = resp.text
		# Try to parse JSON first if returned
		if content_type.startswith("application/json"):
			try:
				data = resp.json()
				# If API returns a URL to download, try following it
				download_url = data.get("url") or data.get("downloadUri") or data.get("downloadUrl")
				if isinstance(download_url, str):
					resp2 = await http.get(download_url)
					text = resp2.text
			except Exception:
				pass
		# Now perform simple containment check against text content (CSV or newline list)
		present: Dict[str, bool] = {}
		for num in req.phone_numbers:
			present[num] = num in text
		return DNCOperationResponse(success=True, message="Checked numbers against DNC list (Genesys)", data={"present": present})


@router.post("/add-dnc-coming-soon", tags=["Coming Soon"], response_model=ComingSoonResponse)
async def add_dnc_placeholder(_: AddToDNCRequest):
	return ComingSoonResponse()


@router.post("/search-dnc", response_model=DNCOperationResponse)
async def search_dnc(request: SearchDNCRequest, bearer_token: Optional[str] = None, client_id: Optional[str] = None, client_secret: Optional[str] = None):
	"""
	Search for a specific phone number in Genesys DNC list.
	Downloads and parses the CSV export to check if the number is on the DNC list.
	"""
	token = bearer_token or await genesys_get_token(client_id, client_secret)
	headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
	api_base = settings.genesys_api_base.rstrip("/")
	
	# First, get the DNC list ID (you mentioned d4a6a02e-4ab9-495b-a141-4c65aee551db)
	dnc_list_id = settings.genesys_dnclist_id or "d4a6a02e-4ab9-495b-a141-4c65aee551db"
	
	# Export the DNC list as CSV
	export_url = f"/api/v2/outbound/dnclists/{dnc_list_id}/export"
	
	async with HttpClient(base_url=api_base) as http:
		resp = await http.get(export_url, headers=headers)
		
		# Parse the CSV response to check if the number is in the list
		is_on_dnc = False
		target_number = request.phone_number
		
		try:
			csv_content = resp.text
			# Simple CSV parsing - look for the phone number in the content
			if target_number in csv_content:
				is_on_dnc = True
		except Exception as e:
			logger.error(f"Error parsing Genesys CSV response: {e}")
		
		return DNCOperationResponse(
			success=True, 
			message=f"Number {target_number} {'IS' if is_on_dnc else 'IS NOT'} on Genesys DNC list", 
			data={
				"phone_number": target_number,
				"is_on_dnc": is_on_dnc,
				"dnc_list_id": dnc_list_id,
				"raw_response": csv_content[:500] + "..." if len(csv_content) > 500 else csv_content  # Truncate for logging
			}
		)


@router.post("/delete-dnc-coming-soon", tags=["Coming Soon"], response_model=ComingSoonResponse)
async def delete_dnc_placeholder(_: DeleteFromDNCRequest):
	return ComingSoonResponse()


@router.post("/upload-dnc-list-coming-soon", tags=["Coming Soon"], response_model=ComingSoonResponse)
async def upload_dnc_placeholder(_: UploadDNCListRequest):
	"""
	Placeholder: The provided sample shows a file upload via a separate uploads service.
	TODO: Implement multi-part file upload to `https://apps.mypurecloud.com/uploads/v2/contactlist` with proper auth.
	"""
	return ComingSoonResponse()


@router.post("/search-by-phone-coming-soon", tags=["Coming Soon"], response_model=ComingSoonResponse)
async def search_by_phone_placeholder(_: SearchByPhoneRequest):
	return ComingSoonResponse()
