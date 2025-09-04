from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, JSON, UniqueConstraint, Index
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


"""
Multi-tenant DNC data model extensions

Key objectives:
- Organizations (tenants) and users
- Catalog of external services and per-organization service connections
- Authoritative DNC entries per organization
- Submission jobs and items
- Propagation attempts to external services with status tracking
"""


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # relationships
    users = relationship("OrgUser", back_populates="organization", cascade="all, delete-orphan")
    services = relationship("OrgService", back_populates="organization", cascade="all, delete-orphan")
    dnc_entries = relationship("DNCEntry", back_populates="organization", cascade="all, delete-orphan")
    jobs = relationship("RemovalJob", back_populates="organization", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name='{self.name}')>"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(320), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    org_links = relationship("OrgUser", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"


class OrgUser(Base):
    __tablename__ = "org_users"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_user"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(50), default="member", nullable=False)  # owner, admin, member
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="users")
    user = relationship("User", back_populates="org_links")


class ServiceCatalog(Base):
    """Global catalog of supported external services (Convoso, Ytel, etc.)."""

    __tablename__ = "service_catalog"
    __table_args__ = (UniqueConstraint("key", name="uq_service_catalog_key"),)

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), nullable=False)  # e.g., 'convoso', 'ringcentral'
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OrgService(Base):
    """Per-organization service connection and settings."""

    __tablename__ = "org_services"
    __table_args__ = (UniqueConstraint("organization_id", "service_key", name="uq_org_service"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    service_key = Column(String(50), nullable=False)
    display_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    credentials = Column(JSON, nullable=True)  # encrypted or secret-managed in production
    settings = Column(JSON, nullable=True)     # misc service-specific settings
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="services")


class DNCEntry(Base):
    """Authoritative DNC list per organization."""

    __tablename__ = "dnc_entries"
    __table_args__ = (
        UniqueConstraint("organization_id", "phone_e164", name="uq_dnc_org_phone"),
        Index("ix_dnc_phone", "phone_e164"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    phone_e164 = Column(String(20), nullable=False)
    reason = Column(String(200), nullable=True)
    source = Column(String(50), nullable=True)  # manual, import, api, tps, freednclist, etc.
    source_service_key = Column(String(50), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    removed_at = Column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization", back_populates="dnc_entries")


class RemovalJob(Base):
    """Submission/batch job to add/remove numbers across services."""

    __tablename__ = "removal_jobs"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    submitted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    total = Column(Integer, default=0, nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending, processing, completed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="jobs")
    items = relationship("RemovalJobItem", back_populates="job", cascade="all, delete-orphan")


class RemovalJobItem(Base):
    __tablename__ = "removal_job_items"
    __table_args__ = (Index("ix_jobitem_phone", "phone_e164"),)

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("removal_jobs.id"), nullable=False)
    phone_e164 = Column(String(20), nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String(20), default="pending", nullable=False)  # pending, processing, completed, failed
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    job = relationship("RemovalJob", back_populates="items")


class PropagationAttempt(Base):
    """Tracks attempts to update external services for a specific phone."""

    __tablename__ = "propagation_attempts"
    __table_args__ = (
        Index("ix_attempt_org_phone", "organization_id", "phone_e164"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    job_item_id = Column(Integer, ForeignKey("removal_job_items.id"), nullable=True)
    phone_e164 = Column(String(20), nullable=False)
    service_key = Column(String(50), nullable=False)
    attempt_no = Column(Integer, default=1, nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending, success, failed
    request_payload = Column(JSON, nullable=True)
    response_payload = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)


class CRMDNCSample(Base):
    """Daily sample of CRM phone numbers vs National DNC and our org DNC."""

    __tablename__ = "crm_dnc_samples"
    __table_args__ = (
        Index("ix_crm_sample_org_date", "organization_id", "sample_date"),
        Index("ix_crm_sample_phone", "phone_e164"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    sample_date = Column(DateTime(timezone=True), nullable=False)
    phone_e164 = Column(String(20), nullable=False)
    in_national_dnc = Column(Boolean, default=False, nullable=False)
    in_org_dnc = Column(Boolean, default=False, nullable=False)
    crm_source = Column(String(50), nullable=True)  # which CRM pulled from
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # No explicit relationships to keep ingestion fast

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


# New Pydantic schemas for multi-tenant entities

class OrganizationBase(BaseModel):
    name: str
    slug: str


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationResponse(OrganizationBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    email: str
    name: str | None = None


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class OrgServiceBase(BaseModel):
    service_key: str
    display_name: str | None = None
    is_active: bool = True
    credentials: Dict[str, Any] | None = None
    settings: Dict[str, Any] | None = None


class OrgServiceCreate(OrgServiceBase):
    organization_id: int


class OrgServiceResponse(OrgServiceBase):
    id: int
    organization_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DNCEntryBase(BaseModel):
    phone_e164: str
    reason: str | None = None
    source: str | None = None
    source_service_key: str | None = None
    notes: str | None = None
    active: bool = True


class DNCEntryCreate(DNCEntryBase):
    organization_id: int
    created_by_user_id: int | None = None


class DNCEntryResponse(DNCEntryBase):
    id: int
    organization_id: int
    created_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime
    removed_at: datetime | None = None

    class Config:
        from_attributes = True


class RemovalJobBase(BaseModel):
    notes: str | None = None
    total: int = 0
    status: str = "pending"


class RemovalJobCreate(RemovalJobBase):
    organization_id: int
    submitted_by_user_id: int | None = None


class RemovalJobResponse(RemovalJobBase):
    id: int
    organization_id: int
    submitted_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RemovalJobItemBase(BaseModel):
    phone_e164: str
    notes: str | None = None
    status: str = "pending"
    result: Dict[str, Any] | None = None


class RemovalJobItemCreate(RemovalJobItemBase):
    job_id: int


class RemovalJobItemResponse(RemovalJobItemBase):
    id: int
    job_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PropagationAttemptResponse(BaseModel):
    id: int
    organization_id: int
    job_item_id: int | None
    phone_e164: str
    service_key: str
    attempt_no: int
    status: str
    request_payload: Dict[str, Any] | None
    response_payload: Dict[str, Any] | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None

    class Config:
        from_attributes = True
