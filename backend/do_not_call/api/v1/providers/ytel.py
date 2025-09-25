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
	final_user = user or settings.ytel_user
	final_pass = password or settings.ytel_password
	if not final_user or not final_pass:
		raise HTTPException(status_code=400, detail="Ytel credentials not configured. Provide 'user' and 'password' or set YTEL_USER/YTEL_PASSWORD in environment.")
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
		return DNCOperationResponse(success=True, message="Added to DNC (Ytel)", data={"raw": text})


@router.post("/search-dnc", response_model=DNCOperationResponse)
async def search_dnc(request: SearchDNCRequest, user: Optional[str] = None, password: Optional[str] = None):
	user, pwd = get_ytel_credentials(user, password)
	base = "https://tra.ytel.com/x5/api/non_agent.php"
	params = {
		"function": "add_lead",
		"user": user,
		"pass": pwd,
		"source": "dncfilter",
		"phone_number": request.phone_number,
		"dnc_check": "Y",
		"campaign_dnc_check": "Y",
		"duplicate_check": "Y",
	}
	async with HttpClient() as http:
		resp = await http.get(base, params=params)
		text = resp.text
		logger.info(f"Ytel search_dnc response: {text}")
		return DNCOperationResponse(success=True, message="Searched DNC (Ytel)", data={"raw": text})


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
