from fastapi import APIRouter, HTTPException
from typing import Optional
from loguru import logger
import base64
from urllib.parse import quote

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
from do_not_call.api.v1.providers.http_client import HttpClient

router = APIRouter()

# Cache for TI Parser auth token
_tiparser_token: Optional[str] = None


async def get_tiparser_token(force_refresh: bool = False) -> Optional[str]:
	"""Login to TI Parser and return auth token."""
	global _tiparser_token
	
	# Return cached token if available and not forcing refresh
	if _tiparser_token and not force_refresh:
		return _tiparser_token
	
	try:
		async with HttpClient() as http:
			login_url = "https://tiparser.onrender.com/auth/login"
			payload = {
				"username": "devops.service@tra.com",
				"password": "TPSZen2025@!"
			}
			resp = await http.post(login_url, json=payload, headers={"Content-Type": "application/json"})
			
			if resp.status_code == 200:
				data = resp.json()
				token = data.get("access_token") or data.get("token")
				if token:
					_tiparser_token = token
					logger.info("Successfully authenticated with TI Parser")
					return token
			
			logger.warning(f"TI Parser login failed: {resp.status_code} - {resp.text}")
			return None
	except Exception as e:
		logger.error(f"TI Parser login error: {e}")
		return None


async def search_tiparser(phone_number: str) -> Optional[dict]:
	"""Search for cases using TI Parser API (searches spouse numbers too)."""
	try:
		logger.info(f"Starting TI Parser search for {phone_number}")
		
		# URL encode the phone number
		encoded_phone = quote(phone_number)
		logger.info(f"Encoded phone number: {encoded_phone}")
		
		async with HttpClient() as http:
			url = f"https://tiparser.onrender.com/case-data/api/case/search/logiqs?query={encoded_phone}"
			headers = {
				"accept": "application/json",
				"x-api-key": "sk_BIWGmwZeahwOyI9ytZNMnZmM_mY1SOcpl4OXlmFpJvA"
			}
			
			logger.info(f"Making TI Parser request to: {url}")
			resp = await http.post(url, headers=headers)
			logger.info(f"TI Parser response status: {resp.status_code}")
			
			# Check if auth is needed
			if resp.status_code == 401 or "Needs Authorization" in resp.text or "Unauthorized" in resp.text:
				logger.info("TI Parser needs authorization, attempting to refresh token")
				token = await get_tiparser_token(force_refresh=True)
				if token:
					# Retry with new token
					resp = await http.post(url, headers=headers)
					logger.info(f"TI Parser retry response status: {resp.status_code}")
				else:
					logger.error("Failed to get TI Parser token for retry")
					return None
			
			if resp.status_code == 200:
				data = resp.json() if resp.headers.get("content-type","").startswith("application/json") else {"raw": resp.text}
				logger.info(f"TI Parser search successful for {phone_number}: {data}")
				return data
			else:
				logger.warning(f"TI Parser search failed: {resp.status_code} - {resp.text}")
				return None
				
	except Exception as e:
		logger.error(f"TI Parser search error for {phone_number}: {e}")
		return None


async def search_logics_direct(phone_number: str, basic_auth_b64: str, headers: dict) -> dict:
	"""Direct search using original Logics API (fallback)."""
	url = f"https://tps.logiqs.com/publicapi/V3/Find/FindCaseByPhone"
	params = {"phone": phone_number}
	async with HttpClient() as http:
		resp = await http.get(url, headers=headers, params=params)
		data = resp.json() if resp.headers.get("content-type","").startswith("application/json") else {"raw": resp.text}
		return data


def get_basic_auth() -> str:
	if not settings.logics_basic_auth_b64:
		raise HTTPException(status_code=400, detail="Logics basic auth (base64) not configured")
	return settings.logics_basic_auth_b64


@router.post("/add-dnc-coming-soon", tags=["Coming Soon"], response_model=ComingSoonResponse)
async def add_dnc_placeholder(_: AddToDNCRequest):
	return ComingSoonResponse()


@router.post("/search-dnc-coming-soon", tags=["Coming Soon"], response_model=ComingSoonResponse)
async def search_dnc_placeholder(_: SearchDNCRequest):
	return ComingSoonResponse()


@router.post("/list-all-dnc-coming-soon", tags=["Coming Soon"], response_model=ComingSoonResponse)
async def list_all_dnc_placeholder(_: ListAllDNCRequest):
	return ComingSoonResponse()


@router.post("/delete-dnc-coming-soon", tags=["Coming Soon"], response_model=ComingSoonResponse)
async def delete_dnc_placeholder(_: DeleteFromDNCRequest):
	return ComingSoonResponse()


class LogicsUpdateCaseRequest(UploadDNCListRequest):
	case_id: int
	status_id: int


@router.post("/update-case", response_model=DNCOperationResponse)
async def update_case(req: LogicsUpdateCaseRequest, basic_auth_b64: Optional[str] = None, cookie: Optional[str] = None):
	b64 = basic_auth_b64 or get_basic_auth()
	headers = {"Content-Type": "application/json", "Authorization": f"Basic {b64}"}
	if cookie or settings.logics_cookie:
		headers["Cookie"] = cookie or settings.logics_cookie
	url = "https://tps.logiqs.com/publicapi/V3/UpdateCase/UpdateCase"
	payload = {"CaseID": req.case_id, "StatusID": req.status_id}
	async with HttpClient() as http:
		resp = await http.post(url, json=payload, headers=headers)
		return DNCOperationResponse(success=True, message="Updated case (Logics)", data=resp.json() if resp.headers.get("content-type","" ).startswith("application/json") else {"raw": resp.text})


@router.get("/test-tiparser")
async def test_tiparser():
	"""Test endpoint to verify TI Parser integration."""
	try:
		result = await search_tiparser("(723)734-7734")
		return {
			"success": True,
			"tiparser_result": result,
			"message": "TI Parser test completed"
		}
	except Exception as e:
		return {
			"success": False,
			"error": str(e),
			"message": "TI Parser test failed"
		}


@router.post("/search-by-phone", response_model=DNCOperationResponse)
async def search_by_phone(request: SearchByPhoneRequest, basic_auth_b64: Optional[str] = None, cookie: Optional[str] = None):
	"""
	Search for Logics cases by phone number.
	Primary: Use TI Parser API (searches spouse numbers too)
	Fallback: Use direct Logics API if TI Parser fails
	"""
	
	# Try TI Parser first (better search, includes spouse numbers)
	logger.info(f"=== LOGICS SEARCH START === Attempting TI Parser search for {request.phone_number}")
	tiparser_data = await search_tiparser(request.phone_number)
	logger.info(f"TI Parser result: {tiparser_data is not None}")
	
	if tiparser_data is not None:
		# TI Parser succeeded - parse and return results
		logger.info(f"Using TI Parser results for {request.phone_number}")
		
		# Check if cases were found in TI Parser response
		is_found = False
		cases = []
		
		if isinstance(tiparser_data, dict):
			# TI Parser might return cases in different structure
			# Try to extract cases from common response patterns
			if tiparser_data.get("cases"):
				cases = tiparser_data.get("cases", [])
				is_found = len(cases) > 0
			elif tiparser_data.get("data"):
				# If data is a list of cases
				if isinstance(tiparser_data.get("data"), list):
					cases = tiparser_data.get("data", [])
					is_found = len(cases) > 0
				# If data contains cases
				elif isinstance(tiparser_data.get("data"), dict) and tiparser_data["data"].get("cases"):
					cases = tiparser_data["data"].get("cases", [])
					is_found = len(cases) > 0
			# Direct Success/Data structure (similar to Logics API)
			elif tiparser_data.get("Success") is True and tiparser_data.get("Data") is not None:
				data_list = tiparser_data.get("Data", [])
				if isinstance(data_list, list) and len(data_list) > 0:
					cases = data_list
					is_found = True
				elif isinstance(data_list, dict) and data_list:
					cases = [data_list]
					is_found = True
		
		return DNCOperationResponse(
			success=True,
			message=f"Number {request.phone_number} {'FOUND' if is_found else 'NOT FOUND'} in Logics database (via TI Parser)",
			data={
				"phone_number": request.phone_number,
				"is_found": is_found,
				"raw_response": {"Data": cases, "Success": is_found},
				"source": "tiparser",
				"tiparser_raw": tiparser_data
			}
		)
	
	# Fallback to direct Logics API
	logger.info(f"TI Parser failed, falling back to direct Logics API for {request.phone_number}")
	
	b64 = basic_auth_b64 or get_basic_auth()
	headers = {"Authorization": f"Basic {b64}"}
	if cookie or settings.logics_cookie:
		headers["Cookie"] = cookie or settings.logics_cookie
	
	try:
		data = await search_logics_direct(request.phone_number, b64, headers)
		
		# Check if the response indicates the number was found
		is_found = False
		if isinstance(data, dict):
			# Check for success indicators in the response
			if data.get("Success") is True and data.get("Data") is not None:
				# Check if Data is a list with items or a non-empty object
				data_list = data.get("Data", [])
				if isinstance(data_list, list) and len(data_list) > 0:
					is_found = True
				elif isinstance(data_list, dict) and data_list:
					is_found = True
		
		return DNCOperationResponse(
			success=True, 
			message=f"Number {request.phone_number} {'FOUND' if is_found else 'NOT FOUND'} in Logics database (via direct API)", 
			data={
				"phone_number": request.phone_number,
				"is_found": is_found,
				"raw_response": data,
				"source": "logics_direct"
			}
		)
	except Exception as e:
		# Handle 404 and other errors gracefully
		logger.error(f"Logics direct search error for {request.phone_number}: {e}")
		return DNCOperationResponse(
			success=True, 
			message=f"Number {request.phone_number} NOT FOUND in Logics database (error occurred)", 
			data={
				"phone_number": request.phone_number,
				"is_found": False,
				"error": str(e),
				"source": "logics_direct"
			}
		)
