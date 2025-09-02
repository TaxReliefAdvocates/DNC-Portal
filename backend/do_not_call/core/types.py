from enum import Enum
from typing import List


class CRMSystem(str, Enum):
    """Supported CRM systems"""
    trackdrive = "trackdrive"
    irslogics = "irslogics"
    listflex = "listflex"
    retriever = "retriever"
    everflow = "everflow"


class CRMStatusType(str, Enum):
    """CRM status types"""
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    retry = "retry"
    cancelled = "cancelled"


class PhoneStatus(str, Enum):
    """Phone number status types"""
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    active = "active"


class ConsentType(str, Enum):
    """Consent types"""
    sms = "sms"
    email = "email"
    phone = "phone"
    marketing = "marketing"


class ConsentStatus(str, Enum):
    """Consent status types"""
    granted = "granted"
    revoked = "revoked"
    pending = "pending"
    expired = "expired"


# CRM System configurations
CRM_SYSTEM_CONFIGS = {
    CRMSystem.trackdrive: {
        "name": "TrackDrive",
        "base_url": "https://api.trackdrive.com",
        "api_key_required": True,
        "rate_limit": 100,  # requests per minute
    },
    CRMSystem.irslogics: {
        "name": "IRSLogics",
        "base_url": "https://api.irslogics.com",
        "api_key_required": True,
        "rate_limit": 100,
    },
    CRMSystem.listflex: {
        "name": "ListFlex",
        "base_url": "https://api.listflex.com",
        "api_key_required": True,
        "rate_limit": 100,
    },
    CRMSystem.retriever: {
        "name": "Retriever",
        "base_url": "https://api.retriever.com",
        "api_key_required": True,
        "rate_limit": 100,
    },
    CRMSystem.everflow: {
        "name": "Everflow",
        "base_url": "https://api.everflow.com",
        "api_key_required": True,
        "rate_limit": 100,
    },
}


def get_crm_system_config(crm_system: CRMSystem) -> dict:
    """Get configuration for a CRM system"""
    return CRM_SYSTEM_CONFIGS.get(crm_system, CRM_SYSTEM_CONFIGS[CRMSystem.other])


def get_all_crm_systems() -> List[CRMSystem]:
    """Get all supported CRM systems"""
    return list(CRMSystem)


def get_crm_system_names() -> List[str]:
    """Get all CRM system names"""
    return [config["name"] for config in CRM_SYSTEM_CONFIGS.values()]
