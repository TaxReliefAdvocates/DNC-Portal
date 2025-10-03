from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
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

router = APIRouter()


def get_ytel_credentials(user: Optional[str] = None, password: Optional[str] = None):
	# Hardcoded credentials since they don't change
	final_user = user or "103"
	final_pass = password or "bHSQPgE7J6nLzX"
	return final_user, final_pass


@router.post("/auth-coming-soon", tags=["Coming Soon"])  # Ytel uses basic auth via params; no token flow
async def ytel_auth_placeholder():
	"""
	Placeholder: Ytel uses user/password via query params per request.
	TODO: Optionally implement a credentials validation ping if Ytel provides one.
	"""
	return ComingSoonResponse()


@router.post("/add-dnc", response_model=DNCOperationResponse)
async def add_to_dnc(request: AddToDNCRequest, user: Optional[str] = None, password: Optional[str] = None):
	user, pwd = get_ytel_credentials(user, password)
	base = "https://tra.ytel.com/x5/api/non_agent.php"
	params = {
		"function": "update_lead",
		"user": user,
		"pass": pwd,
		"source": "dncfilter",
		"status": "DNC",
		"phone_number": request.phone_number,
		"ADDTODNC": "BOTH",
	}
	if request.campaign_id:
		params["CAMPAIGN"] = request.campaign_id
	async with HttpClient() as http:
		resp = await http.get(base, params=params)
		text = resp.text
		logger.info(f"Ytel add_to_dnc response: {text}")
		
		# Parse Ytel response to provide meaningful feedback
		if "Already on GLOBAL DNC" in text:
			return DNCOperationResponse(
				success=True, 
				message=f"Number {request.phone_number} is already on Ytel DNC list", 
				data={"raw": text, "already_on_dnc": True}
			)
		elif "LEADS FOUND IN THE SYSTEM" in text:
			return DNCOperationResponse(
				success=True, 
				message=f"Number {request.phone_number} added to Ytel DNC list", 
				data={"raw": text, "added_to_dnc": True}
			)
		elif "NO MATCHES FOUND IN THE SYSTEM" in text:
			return DNCOperationResponse(
				success=True, 
				message=f"Number {request.phone_number} added to Ytel global DNC (no existing lead)", 
				data={"raw": text, "added_to_global_dnc": True}
			)
		else:
			return DNCOperationResponse(
				success=True, 
				message=f"Number {request.phone_number} processed by Ytel", 
				data={"raw": text}
			)


@router.post("/search-dnc", response_model=DNCOperationResponse)
async def search_dnc(request: SearchDNCRequest, user: Optional[str] = None, password: Optional[str] = None):
	"""
	Two-step DNC check for Ytel:
	1. Check if lead exists
	2. If no lead, check global DNC status
	"""
	user, pwd = get_ytel_credentials(user, password)
	base = "https://tra.ytel.com/x5/api/non_agent.php"
	target_number = request.phone_number
	
	# Step 1: Check if lead exists
	lead_params = {
		"function": "update_lead",
		"user": user,
		"pass": pwd,
		"source": "dncfilter",
		"phone_number": target_number,
		"no_update": "Y",
		"search_method": "PHONE_NUMBER",
	}
	
	async with HttpClient() as http:
		# Step 1: Check for existing lead
		lead_resp = await http.get(base, params=lead_params)
		lead_text = lead_resp.text
		logger.info(f"Ytel lead check response: {lead_text}")
		
		lead_exists = False
		is_on_dnc = False
		status = "unknown"
		
		try:
			if "LEADS FOUND IN THE SYSTEM" in lead_text:
				lead_exists = True
				# Check if the found lead is marked as DNC
				# Ytel returns format: |user|||phone|status_code|0
				# Status codes: 996 = DNC, 999 = DNC, others = active
				if "DNC" in lead_text or "status.*DNC" in lead_text or "|996|" in lead_text or "|999|" in lead_text:
					is_on_dnc = True
					status = "listed"
				else:
					is_on_dnc = False
					status = "not_listed"
			elif "NO MATCHES FOUND IN THE SYSTEM" in lead_text:
				lead_exists = False
				# Step 2: No lead found, check global DNC status using add_lead with duplicate_check
				dnc_params = {
					"function": "add_lead",
					"user": user,
					"pass": pwd,
					"source": "dncfilter",
					"phone_number": target_number,
					"duplicate_check": "Y",  # This will check if number is on DNC
					"status": "DNC"
				}
				
				dnc_resp = await http.get(base, params=dnc_params)
				dnc_text = dnc_resp.text
				logger.info(f"Ytel DNC check response: {dnc_text}")
				
				# Parse DNC check response
				if "DNC" in dnc_text or "ALREADY EXISTS" in dnc_text:
					is_on_dnc = True
					status = "listed"
				else:
					is_on_dnc = False
					status = "not_listed"
			else:
				# If we can't parse, assume not found
				lead_exists = False
				is_on_dnc = False
				status = "unknown"
				
		except Exception as e:
			logger.error(f"Error parsing Ytel response: {e}")
			lead_exists = False
			is_on_dnc = False
			status = "unknown"
		
		# Determine final message
		if status == "listed":
			message = f"Number {target_number} is ON DNC list"
		elif status == "not_listed":
			message = f"Number {target_number} is NOT on DNC list"
		else:
			message = f"Number {target_number} DNC status UNKNOWN"
		
		return DNCOperationResponse(
			success=True, 
			message=message,
			data={
				"phone_number": target_number,
				"is_on_dnc": is_on_dnc,
				"status": status,
				"lead_exists": lead_exists,
				"lead_response": lead_text,
				"dnc_response": dnc_text if not lead_exists else None
			}
		)


@router.post("/list-all-dnc-coming-soon", tags=["Coming Soon"], response_model=ComingSoonResponse)
async def list_all_dnc_placeholder(_: ListAllDNCRequest):
	"""
	Placeholder: List all DNC entries for Ytel.
	TODO: Implement if/when Ytel list endpoint is available.
	"""
	return ComingSoonResponse()


@router.post("/delete-dnc-coming-soon", tags=["Coming Soon"], response_model=ComingSoonResponse)
async def delete_dnc_placeholder(_: DeleteFromDNCRequest):
	"""
	Placeholder: Delete from DNC for Ytel.
	TODO: Implement if/when delete endpoint is available.
	"""
	return ComingSoonResponse()


class YtelUploadRequest(UploadDNCListRequest):
	phone_number: str
	list_id: Optional[str] = None
	first_name: Optional[str] = None
	last_name: Optional[str] = None


@router.post("/upload-dnc", response_model=DNCOperationResponse)
async def upload_dnc_list(request: YtelUploadRequest, user: Optional[str] = None, password: Optional[str] = None):
	user, pwd = get_ytel_credentials(user, password)
	base = "https://tra.ytel.com/x5/api/non_agent.php"
	params = {
		"function": "add_lead",
		"user": user,
		"pass": pwd,
		"source": "dncfilter",
		"phone_number": request.phone_number,
		"duplicate_check": "N",
	}
	if request.list_id:
		params["list_id"] = request.list_id
	if request.first_name:
		params["first_name"] = request.first_name
	if request.last_name:
		params["last_name"] = request.last_name
	async with HttpClient() as http:
		resp = await http.get(base, params=params)
		text = resp.text
		logger.info(f"Ytel upload_dnc response: {text}")
		return DNCOperationResponse(success=True, message="Uploaded DNC entry (Ytel)", data={"raw": text})


@router.post("/search-by-phone-coming-soon", tags=["Coming Soon"], response_model=ComingSoonResponse)
async def search_by_phone_placeholder(_: SearchByPhoneRequest):
	"""
	Placeholder: Search by phone for Ytel.
	TODO: Implement when supported endpoint details are available.
	"""
	return ComingSoonResponse()
