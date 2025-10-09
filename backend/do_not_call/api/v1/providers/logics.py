from fastapi import APIRouter, HTTPException
from typing import Optional
from loguru import logger
import base64

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


@router.post("/search-by-phone", response_model=DNCOperationResponse)
async def search_by_phone(request: SearchByPhoneRequest, basic_auth_b64: Optional[str] = None, cookie: Optional[str] = None):
	b64 = basic_auth_b64 or get_basic_auth()
	headers = {"Authorization": f"Basic {b64}"}
	if cookie or settings.logics_cookie:
		headers["Cookie"] = cookie or settings.logics_cookie
	url = f"https://tps.logiqs.com/publicapi/V3/Find/FindCaseByPhone"
	
	# Normalize phone number - strip all non-digit characters
	normalized_phone = ''.join(filter(str.isdigit, request.phone_number))
	
	# Try different formats to find the case
	phone_formats = [
		normalized_phone,  # 7237347734
		f"1{normalized_phone}" if len(normalized_phone) == 10 else normalized_phone,  # 17237347734
		f"+1{normalized_phone}" if len(normalized_phone) == 10 else f"+{normalized_phone}",  # +17237347734
	]
	
	# Remove duplicates while preserving order
	phone_formats = list(dict.fromkeys(phone_formats))
	
	logger.info(f"Searching Logics for phone {request.phone_number}, trying formats: {phone_formats}")
	
	# Try each format until we find a match
	async with HttpClient() as http:
		last_error = None
		last_data = None
		
		for phone_format in phone_formats:
			params = {"phone": phone_format}
			try:
				logger.info(f"Trying Logics search with format: {phone_format}")
				resp = await http.get(url, headers=headers, params=params)
				data = resp.json() if resp.headers.get("content-type","").startswith("application/json") else {"raw": resp.text}
				last_data = data
				
				# Check if the response indicates the number was found
				is_found = False
				if isinstance(data, dict):
					# Check for success indicators in the response
					if data.get("Success") is True and data.get("Data") is not None:
						# Check if Data is a list with items or a non-empty object
						data_list = data.get("Data", [])
						if isinstance(data_list, list) and len(data_list) > 0:
							is_found = True
							logger.info(f"Found case(s) in Logics with format {phone_format}: {len(data_list)} case(s)")
						elif isinstance(data_list, dict) and data_list:
							is_found = True
							logger.info(f"Found case in Logics with format {phone_format}")
				
				# If we found a match, return immediately
				if is_found:
					return DNCOperationResponse(
						success=True, 
						message=f"Number {request.phone_number} FOUND in Logics database (format: {phone_format})", 
						data={
							"phone_number": request.phone_number,
							"is_found": is_found,
							"raw_response": data,
							"format_used": phone_format
						}
					)
			except Exception as e:
				# Log error but continue trying other formats
				logger.warning(f"Logics search error for format {phone_format}: {e}")
				last_error = e
				continue
		
		# If we exhausted all formats without finding a match, return not found
		return DNCOperationResponse(
			success=True, 
			message=f"Number {request.phone_number} NOT FOUND in Logics database (tried formats: {', '.join(phone_formats)})", 
			data={
				"phone_number": request.phone_number,
				"is_found": False,
				"raw_response": last_data,
				"formats_tried": phone_formats,
				"last_error": str(last_error) if last_error else None
			}
		)
