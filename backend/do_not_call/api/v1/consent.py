from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from loguru import logger

from ...core.database import get_db
from ...core.models import (
    Consent, ConsentCreate, ConsentUpdate, ConsentResponse,
    PhoneNumber
)

router = APIRouter()


@router.post("/", response_model=ConsentResponse)
async def create_consent(
    consent_data: ConsentCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new consent record
    
    - **phone_number_id**: ID of the phone number
    - **consent_type**: Type of consent (sms, email, phone, marketing)
    - **status**: Status of consent (granted, revoked, pending, expired)
    - **source**: Source of consent (web_form, phone_call, email, etc.)
    - **notes**: Optional notes
    """
    # Verify phone number exists
    phone_number = db.query(PhoneNumber).filter(
        PhoneNumber.id == consent_data.phone_number_id
    ).first()
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Set timestamps based on status
    granted_at = None
    revoked_at = None
    
    if consent_data.status == "granted":
        granted_at = datetime.utcnow()
    elif consent_data.status == "revoked":
        revoked_at = datetime.utcnow()
    
    # Create consent record
    consent = Consent(
        phone_number_id=consent_data.phone_number_id,
        consent_type=consent_data.consent_type,
        status=consent_data.status,
        source=consent_data.source,
        notes=consent_data.notes,
        granted_at=granted_at,
        revoked_at=revoked_at
    )
    
    db.add(consent)
    db.commit()
    db.refresh(consent)
    
    logger.info(f"Created consent record for phone {consent_data.phone_number_id}")
    
    return ConsentResponse.from_orm(consent)


@router.get("/", response_model=List[ConsentResponse])
async def get_consents(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    consent_type: Optional[str] = Query(None, description="Filter by consent type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    phone_number_id: Optional[int] = Query(None, description="Filter by phone number ID"),
    db: Session = Depends(get_db)
):
    """
    Get list of consent records with optional filtering
    """
    query = db.query(Consent)
    
    # Apply filters
    if consent_type:
        query = query.filter(Consent.consent_type == consent_type)
    
    if status:
        query = query.filter(Consent.status == status)
    
    if phone_number_id:
        query = query.filter(Consent.phone_number_id == phone_number_id)
    
    # Apply pagination
    consents = query.offset(skip).limit(limit).all()
    
    return [ConsentResponse.from_orm(consent) for consent in consents]


@router.get("/{phone_number}", response_model=List[ConsentResponse])
async def get_consent_by_phone(
    phone_number: str,
    db: Session = Depends(get_db)
):
    """
    Get consent records for a specific phone number
    """
    # Find phone number record
    phone_record = db.query(PhoneNumber).filter(
        PhoneNumber.phone_number == phone_number
    ).first()
    
    if not phone_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Get all consent records for this phone number
    consents = db.query(Consent).filter(
        Consent.phone_number_id == phone_record.id
    ).all()
    
    return [ConsentResponse.from_orm(consent) for consent in consents]


@router.get("/{consent_id}", response_model=ConsentResponse)
async def get_consent(
    consent_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific consent record by ID
    """
    consent = db.query(Consent).filter(Consent.id == consent_id).first()
    
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consent record not found"
        )
    
    return ConsentResponse.from_orm(consent)


@router.put("/{consent_id}", response_model=ConsentResponse)
async def update_consent(
    consent_id: int,
    update_data: ConsentUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a consent record
    
    - **status**: New status for the consent
    - **notes**: Updated notes
    - **granted_at**: When consent was granted
    - **revoked_at**: When consent was revoked
    """
    consent = db.query(Consent).filter(Consent.id == consent_id).first()
    
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consent record not found"
        )
    
    # Update fields
    if update_data.status is not None:
        consent.status = update_data.status
        
        # Update timestamps based on status change
        if update_data.status == "granted" and consent.granted_at is None:
            consent.granted_at = datetime.utcnow()
        elif update_data.status == "revoked" and consent.revoked_at is None:
            consent.revoked_at = datetime.utcnow()
    
    if update_data.notes is not None:
        consent.notes = update_data.notes
    
    if update_data.granted_at is not None:
        consent.granted_at = update_data.granted_at
    
    if update_data.revoked_at is not None:
        consent.revoked_at = update_data.revoked_at
    
    db.commit()
    db.refresh(consent)
    
    logger.info(f"Updated consent record {consent_id}: status={update_data.status}")
    
    return ConsentResponse.from_orm(consent)


@router.delete("/{consent_id}")
async def delete_consent(
    consent_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a consent record
    """
    consent = db.query(Consent).filter(Consent.id == consent_id).first()
    
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consent record not found"
        )
    
    db.delete(consent)
    db.commit()
    
    logger.info(f"Deleted consent record {consent_id}")
    
    return {"message": "Consent record deleted successfully"}


@router.get("/history/{phone_number}", response_model=List[ConsentResponse])
async def get_consent_history(
    phone_number: str,
    db: Session = Depends(get_db)
):
    """
    Get complete consent history for a phone number
    """
    # Find phone number record
    phone_record = db.query(PhoneNumber).filter(
        PhoneNumber.phone_number == phone_number
    ).first()
    
    if not phone_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Get all consent records for this phone number, ordered by creation date
    consents = db.query(Consent).filter(
        Consent.phone_number_id == phone_record.id
    ).order_by(Consent.created_at.desc()).all()
    
    return [ConsentResponse.from_orm(consent) for consent in consents]


@router.get("/stats/summary")
async def get_consent_stats(db: Session = Depends(get_db)):
    """
    Get summary statistics for consent records
    """
    total = db.query(Consent).count()
    granted = db.query(Consent).filter(Consent.status == "granted").count()
    revoked = db.query(Consent).filter(Consent.status == "revoked").count()
    pending = db.query(Consent).filter(Consent.status == "pending").count()
    expired = db.query(Consent).filter(Consent.status == "expired").count()
    
    # Stats by consent type
    sms_consents = db.query(Consent).filter(Consent.consent_type == "sms").count()
    email_consents = db.query(Consent).filter(Consent.consent_type == "email").count()
    phone_consents = db.query(Consent).filter(Consent.consent_type == "phone").count()
    marketing_consents = db.query(Consent).filter(Consent.consent_type == "marketing").count()
    
    return {
        "total": total,
        "granted": granted,
        "revoked": revoked,
        "pending": pending,
        "expired": expired,
        "by_type": {
            "sms": sms_consents,
            "email": email_consents,
            "phone": phone_consents,
            "marketing": marketing_consents
        },
        "grant_rate": (granted / total * 100) if total > 0 else 0
    }



