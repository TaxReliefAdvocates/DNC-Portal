from __future__ import annotations

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class PhoneNumberFormatter:
    @staticmethod
    def to_digits_only(phone_number: str) -> str:
        return ''.join(ch for ch in str(phone_number) if ch.isdigit())

    @staticmethod
    def to_e164(phone_number: str) -> str:
        digits = PhoneNumberFormatter.to_digits_only(phone_number)
        if len(digits) == 11 and digits.startswith('1'):
            return f"+{digits}"
        if len(digits) == 10:
            return f"+1{digits}"
        if str(phone_number).startswith('+'):
            return str(phone_number)
        raise ValueError("Invalid US phone number format")

    @staticmethod
    def to_service_format(phone_number: str, service: str) -> str:
        service = (service or '').lower()
        if service in {"convoso", "ytel"}:
            return PhoneNumberFormatter.to_digits_only(phone_number)
        if service in {"ringcentral"}:
            return PhoneNumberFormatter.to_e164(phone_number)
        # Default: digits only
        return PhoneNumberFormatter.to_digits_only(phone_number)


class BaseDNCEntry(BaseModel):
    phone_number: str
    status: str
    date_added: Optional[datetime] = None
    service_specific_id: Optional[str] = None


class BaseDNCSearchResponse(BaseModel):
    success: bool
    found: bool
    total_count: int = 0
    entries: List[BaseDNCEntry] = Field(default_factory=list)
    service_name: str


class BaseDNCOperationResponse(BaseModel):
    success: bool
    message: str
    phone_number: str
    operation: str
    service_name: str
    details: Optional[Dict[str, Any]] = None


class DNCServiceException(Exception):
    def __init__(self, service: str, operation: str, phone_number: str, details: str):
        super().__init__(details)
        self.service = service
        self.operation = operation
        self.phone_number = phone_number
        self.details = details


class AuthenticationError(DNCServiceException):
    pass


class PhoneNumberFormatError(DNCServiceException):
    pass


class ServiceUnavailableError(DNCServiceException):
    pass


class DuplicateEntryError(DNCServiceException):
    pass


class NotFoundError(DNCServiceException):
    pass


class UnsupportedOperationError(DNCServiceException):
    pass


