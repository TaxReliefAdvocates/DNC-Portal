from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from .types import CRMSystem, CRMStatusType, PhoneStatus, ConsentType, ConsentStatus
from .database import Base


class PhoneNumber(Base):
    """Phone number model for tracking removal requests"""
    __tablename__ = "phone_numbers"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), unique=True, index=True, nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending, processing, completed, failed, cancelled
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    crm_statuses = relationship("CRMStatus", back_populates="phone_number", cascade="all, delete-orphan")
    consents = relationship("Consent", back_populates="phone_number", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<PhoneNumber(id={self.id}, phone_number='{self.phone_number}', status='{self.status}')>"


class CRMStatus(Base):
    """CRM status model for tracking removal requests across different CRM systems"""
    __tablename__ = "crm_statuses"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number_id = Column(Integer, ForeignKey("phone_numbers.id"), nullable=False)
    crm_system = Column(String(50), nullable=False)  # trackdrive, everysource, other
    status = Column(String(20), default="pending", nullable=False)  # pending, processing, completed, failed, retry
    response_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    phone_number = relationship("PhoneNumber", back_populates="crm_statuses")
    
    def __repr__(self):
        return f"<CRMStatus(id={self.id}, crm_system='{self.crm_system}', status='{self.status}')>"


class Consent(Base):
    """Consent model for tracking messaging consent"""
    __tablename__ = "consents"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number_id = Column(Integer, ForeignKey("phone_numbers.id"), nullable=False)
    consent_type = Column(String(20), nullable=False)  # sms, email, phone, marketing
    status = Column(String(20), default="pending", nullable=False)  # granted, revoked, pending, expired
    source = Column(String(100), nullable=False)  # web_form, phone_call, email, etc.
    notes = Column(Text, nullable=True)
    granted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    phone_number = relationship("PhoneNumber", back_populates="consents")
    
    def __repr__(self):
        return f"<Consent(id={self.id}, consent_type='{self.consent_type}', status='{self.status}')>"


class AuditLog(Base):
    """Audit log model for tracking all operations"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(50), nullable=False)  # create, update, delete, etc.
    table_name = Column(String(50), nullable=False)  # phone_numbers, crm_statuses, consents
    record_id = Column(Integer, nullable=True)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    user_id = Column(String(100), nullable=True)  # API key or user identifier
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', table_name='{self.table_name}')>"


class APIRateLimit(Base):
    """API rate limiting model"""
    __tablename__ = "api_rate_limits"
    
    id = Column(Integer, primary_key=True, index=True)
    api_key = Column(String(100), nullable=False, index=True)
    endpoint = Column(String(100), nullable=False)
    request_count = Column(Integer, default=1, nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<APIRateLimit(id={self.id}, api_key='{self.api_key}', endpoint='{self.endpoint}')>"


# Pydantic models for API requests/responses
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class PhoneNumberBase(BaseModel):
    phone_number: str = Field(..., description="Phone number in E.164 format")
    notes: Optional[str] = Field(None, description="Optional notes about the phone number")


class PhoneNumberCreate(PhoneNumberBase):
    pass


class PhoneNumberUpdate(BaseModel):
    status: Optional[str] = Field(None, description="New status for the phone number")
    notes: Optional[str] = Field(None, description="Updated notes")


class PhoneNumberResponse(PhoneNumberBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BulkPhoneNumberRequest(BaseModel):
    phone_numbers: List[str] = Field(..., description="List of phone numbers to add")
    notes: Optional[str] = Field(None, description="Optional notes for all phone numbers")


class BulkPhoneNumberResponse(BaseModel):
    success_count: int
    failed_count: int
    phone_numbers: List[PhoneNumberResponse]
    errors: List[str]


class CRMStatusBase(BaseModel):
    crm_system: str = Field(..., description="CRM system name")
    status: str = Field(..., description="Status of the removal request")
    response_data: Optional[Dict[str, Any]] = Field(None, description="Response data from CRM")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class CRMStatusCreate(CRMStatusBase):
    phone_number_id: int


class CRMStatusUpdate(BaseModel):
    status: Optional[str] = None
    response_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: Optional[int] = None
    processed_at: Optional[datetime] = None


class CRMStatusResponse(CRMStatusBase):
    id: int
    phone_number_id: int
    retry_count: int
    processed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ConsentBase(BaseModel):
    consent_type: str = Field(..., description="Type of consent")
    status: str = Field(..., description="Status of consent")
    source: str = Field(..., description="Source of consent")
    notes: Optional[str] = Field(None, description="Optional notes")


class ConsentCreate(ConsentBase):
    phone_number_id: int


class ConsentUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class ConsentResponse(ConsentBase):
    id: int
    phone_number_id: int
    granted_at: Optional[datetime]
    revoked_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class RemovalStats(BaseModel):
    total_processed: int
    successful_removals: int
    failed_removals: int
    pending_removals: int
    success_rate: float
    average_processing_time: float


class ProcessingTimeStats(BaseModel):
    crm_system: str
    average_time: float
    min_time: float
    max_time: float
    total_requests: int


class ErrorRateStats(BaseModel):
    crm_system: str
    error_count: int
    total_requests: int
    error_rate: float
    common_errors: List[str]
