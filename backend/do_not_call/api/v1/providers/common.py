from typing import Dict, Optional, List
from pydantic import BaseModel, Field


class PageInfo(BaseModel):
	page: int = 1
	per_page: int = Field(default=50, ge=1, le=1000)
	total: Optional[int] = None


class ComingSoonResponse(BaseModel):
	success: bool = False
	message: str = "This endpoint is coming soon"
	status: str = "not_implemented"


class DNCOperationResponse(BaseModel):
	success: bool
	message: str
	data: Optional[Dict] = None
	page_info: Optional[PageInfo] = None


class AddToDNCRequest(BaseModel):
	phone_number: str
	campaign_id: Optional[str] = None
	phone_code: Optional[str] = None


class SearchDNCRequest(BaseModel):
	phone_number: str
	phone_code: Optional[str] = None
	offset: Optional[int] = 0
	limit: Optional[int] = 50


class SearchMultipleDNCRequest(BaseModel):
	phone_numbers: List[str]
	phone_code: Optional[str] = None
	offset: Optional[int] = 0
	limit: Optional[int] = 50


class ListAllDNCRequest(BaseModel):
	page: int = 1
	per_page: int = 50
	status: Optional[str] = None


class DeleteFromDNCRequest(BaseModel):
	phone_number: Optional[str] = None
	phone_code: Optional[str] = None
	resource_id: Optional[str] = None
	campaign_id: Optional[str] = None


class UploadDNCListRequest(BaseModel):
	list_name: Optional[str] = None
	entries: Optional[List[str]] = None


class SearchByPhoneRequest(BaseModel):
	phone_number: str
	phone_code: Optional[str] = None
