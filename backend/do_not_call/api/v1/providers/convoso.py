from fastapi import APIRouter, HTTPException
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


def get_token(token: Optional[str] = None) -> str:
	final = token or settings.convoso_auth_token
	if not final:
		raise HTTPException(status_code=400, detail="Convoso auth_token required. Provide 'auth_token' or set CONVOSO_AUTH_TOKEN.")
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
async def add_to_dnc(request: AddToDNCRequest, auth_token: Optional[str] = None):
	token = get_token(auth_token)
	url = "https://api.convoso.com/v1/dnc/insert"
	params = {"auth_token": token, "phone_number": request.phone_number}
	if request.phone_code:
		params["phone_code"] = request.phone_code
	async with HttpClient() as http:
		resp = await http.get(url, params=params)
		text = resp.text
		logger.info(f"Convoso add_to_dnc response: {text}")
		return DNCOperationResponse(success=True, message="Added to DNC (Convoso)", data={"raw": text})


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


@router.post("/list-all-dnc-coming-soon", tags=["Coming Soon"], response_model=ComingSoonResponse)
async def list_all_dnc_placeholder(_: ListAllDNCRequest):
	return ComingSoonResponse()


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
	token = get_token(auth_token)
	url = "https://api.convoso.com/v1/leads/search"
	params = {
		"auth_token": token,
		"offset": 0,
		"limit": 10,
		"phone_number": request.phone_number,
	}
	async with HttpClient() as http:
		resp = await http.get(url, params=params)
		text = resp.text
		logger.info(f"Convoso search_by_phone response: {text}")
		return DNCOperationResponse(success=True, message="Searched by phone (Convoso)", data={"raw": text})
