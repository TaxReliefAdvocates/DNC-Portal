from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional
from loguru import logger

from do_not_call.core.database import get_db
from do_not_call.core.auth import get_principal, Principal

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

router = APIRouter()


def get_token(token: Optional[str] = None) -> str:
	final = token or settings.convoso_auth_token
	if not final:
		raise HTTPException(status_code=400, detail="Convoso auth_token required. Provide 'auth_token' or set CONVOSO_AUTH_TOKEN.")
	return final

def get_leads_token(token: Optional[str] = None) -> str:
	"""Get token specifically for leads API endpoints"""
	final = token or getattr(settings, 'convoso_token_leads', None) or settings.convoso_auth_token
	if not final:
		raise HTTPException(status_code=400, detail="Convoso leads token required. Provide 'auth_token' or set CONVOSO_TOKEN_LEADS.")
	return final


@router.post("/auth", response_model=DNCOperationResponse)
async def auth(auth_token: Optional[str] = None):
	"""
	Placeholder: In Convoso, an auth_token is provided (e.g., via panel/cookies). Echo back for clarity.
	"""
	if not auth_token and not settings.convoso_auth_token:
		raise HTTPException(status_code=400, detail="auth_token required")
	return DNCOperationResponse(success=True, message="Using Convoso auth_token", data={"auth_token": auth_token or settings.convoso_auth_token})


@router.post("/auth-coming-soon", tags=["Coming Soon"])  # Backward placeholder
async def convoso_auth_placeholder():
	return ComingSoonResponse()


@router.post("/add-dnc", response_model=DNCOperationResponse)
async def add_to_dnc(request: AddToDNCRequest, auth_token: Optional[str] = None, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
	token = get_token(auth_token)
	url = "https://api.convoso.com/v1/dnc/insert"
	params = {"auth_token": token, "phone_number": request.phone_number}
	if request.phone_code:
		params["phone_code"] = request.phone_code
	
	# Create propagation attempt for tracking
	from ...core.models import PropagationAttempt
	from datetime import datetime
	from ...core.utils import normalize_phone_to_e164_digits
	
	phone_e164 = normalize_phone_to_e164_digits(f"{request.phone_code or ''}{request.phone_number}")
	
	try:
		async with HttpClient() as http:
			resp = await http.get(url, params=params)
			text = resp.text
			logger.info(f"Convoso add_to_dnc response: {text}")
			
			# Create propagation attempt record
			attempt = PropagationAttempt(
				organization_id=principal.organization_id,
				phone_e164=phone_e164,
				service_key="convoso",
				attempt_no=1,
				status="success",
				request_payload={"phone_number": phone_e164, "action": "add_to_dnc"},
				response_payload={"raw": text},
				started_at=datetime.utcnow(),
				finished_at=datetime.utcnow(),
			)
			db.add(attempt)
			db.commit()
			
			return DNCOperationResponse(success=True, message="Added to DNC (Convoso)", data={"raw": text})
			
	except Exception as e:
		# Create failed propagation attempt record
		attempt = PropagationAttempt(
			organization_id=principal.organization_id,
			phone_e164=phone_e164,
			service_key="convoso",
			attempt_no=1,
			status="failed",
			request_payload={"phone_number": phone_e164, "action": "add_to_dnc"},
			error_message=str(e),
			started_at=datetime.utcnow(),
			finished_at=datetime.utcnow(),
		)
		db.add(attempt)
		db.commit()
		
		raise HTTPException(status_code=500, detail=f"Failed to add to Convoso DNC: {str(e)}")


@router.post("/search-dnc", response_model=DNCOperationResponse)
async def search_dnc(request: SearchDNCRequest, auth_token: Optional[str] = None):
	"""
	Search for a specific phone number in Convoso DNC list.
	Returns true/false if the number is found on the DNC list.
	"""
	token = get_token(auth_token)
	url = "https://api.convoso.com/v1/dnc/search"
	params = {
		"auth_token": token,
		"phone_number": request.phone_number,
		"offset": 0,
		"limit": 1000,  # Get more results to search through
	}
	if request.phone_code:
		params["phone_code"] = request.phone_code
	
	async with HttpClient() as http:
		resp = await http.get(url, params=params)
		text = resp.text
		logger.info(f"Convoso search_dnc response: {text}")
		
		# Parse the response to check if the specific number is in the DNC list
		is_on_dnc = False
		try:
			# The response should contain a list of DNC numbers
			# We need to check if our target number is in that list
			if request.phone_number in text:
				is_on_dnc = True
		except Exception as e:
			logger.error(f"Error parsing Convoso response: {e}")
		
		return DNCOperationResponse(
			success=True, 
			message=f"Number {request.phone_number} {'IS' if is_on_dnc else 'IS NOT'} on Convoso DNC list", 
			data={
				"phone_number": request.phone_number,
				"is_on_dnc": is_on_dnc,
				"raw_response": text
			}
		)


@router.post("/list-all-dnc", response_model=DNCOperationResponse)
async def list_all_dnc(request: ListAllDNCRequest, auth_token: Optional[str] = None):
	"""
	Retrieve all DNC numbers from Convoso.
	This will be our master DNC list for syncing across all providers.
	"""
	token = get_leads_token(auth_token)
	url = "https://api.convoso.com/v1/leads/search"
	params = {
		"auth_token": token,
		"status": "DNC",
		"limit": 1000,  # Get up to 1000 DNC records
		"offset": 0
	}
	
	# Add cookie header for API access
	headers = {
		"Cookie": "APIUBUNTUBACKEND=apiapp111"
	}
	
	async with HttpClient() as http:
		resp = await http.get(url, params=params, headers=headers)
		data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw": resp.text}
		logger.info(f"Convoso list_all_dnc response: {len(str(data))} characters")
		
		# Extract phone numbers from the response
		dnc_numbers = []
		if isinstance(data, dict) and "data" in data:
			entries = data["data"].get("entries", [])
			for entry in entries:
				if entry.get("status") == "DNC" and entry.get("phone_number"):
					dnc_numbers.append({
						"phone_number": entry["phone_number"],
						"lead_id": entry.get("id"),
						"status": entry.get("status"),
						"created_at": entry.get("created_at"),
						"modified_at": entry.get("modified_at"),
						"campaign_name": entry.get("campaign_name"),
						"first_name": entry.get("first_name"),
						"last_name": entry.get("last_name")
					})
		
		return DNCOperationResponse(
			success=True, 
			message=f"Retrieved {len(dnc_numbers)} DNC numbers from Convoso", 
			data={
				"total_dnc_numbers": len(dnc_numbers),
				"dnc_numbers": dnc_numbers,
				"raw_response": data
			}
		)


@router.post("/delete-dnc", response_model=DNCOperationResponse)
async def delete_from_dnc(request: DeleteFromDNCRequest, auth_token: Optional[str] = None):
	token = get_token(auth_token)
	url = "https://api.convoso.com/v1/dnc/delete"
	params = {
		"auth_token": token,
		"campaign_id": request.campaign_id or 0,
	}
	if request.phone_number:
		params["phone_number"] = request.phone_number
	if request.phone_code:
		params["phone_code"] = request.phone_code
	async with HttpClient() as http:
		resp = await http.get(url, params=params)
		text = resp.text
		logger.info(f"Convoso delete_dnc response: {text}")
		return DNCOperationResponse(success=True, message="Deleted from DNC (Convoso)", data={"raw": text})


@router.post("/upload-dnc-list-coming-soon", tags=["Coming Soon"], response_model=ComingSoonResponse)
async def upload_dnc_placeholder(_: UploadDNCListRequest):
	return ComingSoonResponse()


@router.post("/search-by-phone", response_model=DNCOperationResponse)
async def search_by_phone(request: SearchByPhoneRequest, auth_token: Optional[str] = None):
	"""
	Search for leads by phone number in Convoso.
	This helps identify if a number has multiple lead records that need to be updated to DNC status.
	"""
	token = get_leads_token(auth_token)
	url = "https://api.convoso.com/v1/leads/search"
	params = {
		"auth_token": token,
		"offset": 0,
		"limit": 100,  # Get more results to find all leads with this number
		"phone_number": request.phone_number,
	}
	
	# Add cookie header for API access
	headers = {
		"Cookie": "APIUBUNTUBACKEND=apiapp111"
	}
	
	async with HttpClient() as http:
		resp = await http.get(url, params=params, headers=headers)
		data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw": resp.text}
		logger.info(f"Convoso search_by_phone response: {len(str(data))} characters")
		
		# Extract leads from the response
		leads = []
		if isinstance(data, dict) and "data" in data:
			entries = data["data"].get("entries", [])
			for entry in entries:
				if entry.get("phone_number") == request.phone_number:
					leads.append({
						"lead_id": entry.get("id"),
						"phone_number": entry.get("phone_number"),
						"status": entry.get("status"),
						"first_name": entry.get("first_name"),
						"last_name": entry.get("last_name"),
						"email": entry.get("email"),
						"campaign_name": entry.get("campaign_name"),
						"created_at": entry.get("created_at"),
						"modified_at": entry.get("modified_at"),
						"called_count": entry.get("called_count"),
						"last_called": entry.get("last_called")
					})
		
		# Check if any leads are not already DNC
		non_dnc_leads = [lead for lead in leads if lead["status"] != "DNC"]
		
		return DNCOperationResponse(
			success=True, 
			message=f"Found {len(leads)} leads for phone number {request.phone_number}, {len(non_dnc_leads)} need DNC update", 
			data={
				"phone_number": request.phone_number,
				"total_leads": len(leads),
				"dnc_leads": len(leads) - len(non_dnc_leads),
				"non_dnc_leads": len(non_dnc_leads),
				"leads": leads,
				"needs_dnc_update": non_dnc_leads,
				"raw_response": data
			}
		)
