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


@router.post("/add-dnc-coming-soon", tags=["Coming Soon"], response_model=ComingSoonResponse)
async def add_dnc_placeholder(_: AddToDNCRequest):
	return ComingSoonResponse()


@router.post("/search-dnc-coming-soon", tags=["Coming Soon"], response_model=ComingSoonResponse)
async def search_dnc_placeholder(_: SearchDNCRequest):
	return ComingSoonResponse()


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
