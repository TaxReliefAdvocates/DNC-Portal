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
	params = {"phone": request.phone_number}
	async with HttpClient() as http:
		resp = await http.get(url, headers=headers, params=params)
		return DNCOperationResponse(success=True, message="Searched by phone (Logics)", data=resp.json() if resp.headers.get("content-type","" ).startswith("application/json") else {"raw": resp.text})
