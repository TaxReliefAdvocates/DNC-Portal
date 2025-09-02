from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import re
from loguru import logger

from ...core.database import get_db
from ...core.models import (
    PhoneNumber, PhoneNumberCreate, PhoneNumberUpdate, PhoneNumberResponse,
    BulkPhoneNumberRequest, BulkPhoneNumberResponse
)

router = APIRouter()


def validate_phone_number(phone: str) -> str:
    """Validate and normalize phone number"""
    # Remove all non-digit characters
    cleaned = re.sub(r'\D', '', phone)
    
    # Check if it's a valid US phone number (10 or 11 digits)
    if len(cleaned) == 11 and cleaned.startswith('1'):
        # Remove country code
        cleaned = cleaned[1:]
    
    if len(cleaned) != 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid phone number format: {phone}. Must be 10 digits."
        )
    
    # Format as (XXX) XXX-XXXX
    return f"({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:]}"


@router.post("/bulk", response_model=BulkPhoneNumberResponse)
async def add_bulk_phone_numbers(
    request: BulkPhoneNumberRequest,
    db: Session = Depends(get_db)
):
    """
    Add multiple phone numbers for removal processing
    
    - **phone_numbers**: List of phone numbers to add
    - **notes**: Optional notes for all phone numbers
    """
    success_count = 0
    failed_count = 0
    phone_numbers = []
    errors = []
    
    for phone in request.phone_numbers:
        try:
            # Validate and normalize phone number
            normalized_phone = validate_phone_number(phone)
            
            # Check if phone number already exists
            existing = db.query(PhoneNumber).filter(
                PhoneNumber.phone_number == normalized_phone
            ).first()
            
            if existing:
                errors.append(f"Phone number {phone} already exists")
                failed_count += 1
                continue
            
            # Create new phone number record
            db_phone = PhoneNumber(
                phone_number=normalized_phone,
                notes=request.notes,
                status="pending"
            )
            db.add(db_phone)
            db.commit()
            db.refresh(db_phone)
            
            phone_numbers.append(PhoneNumberResponse.from_orm(db_phone))
            success_count += 1
            
            logger.info(f"Added phone number: {normalized_phone}")
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            errors.append(f"Error processing {phone}: {str(e)}")
            failed_count += 1
            logger.error(f"Error processing phone number {phone}: {e}")
    
    return BulkPhoneNumberResponse(
        success_count=success_count,
        failed_count=failed_count,
        phone_numbers=phone_numbers,
        errors=errors
    )


@router.get("/", response_model=List[PhoneNumberResponse])
async def get_phone_numbers(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in phone number or notes"),
    db: Session = Depends(get_db)
):
    """
    Get list of phone numbers with optional filtering
    
    - **skip**: Number of records to skip for pagination
    - **limit**: Number of records to return (max 1000)
    - **status**: Filter by status (pending, processing, completed, failed, cancelled)
    - **search**: Search in phone number or notes
    """
    query = db.query(PhoneNumber)
    
    # Apply filters
    if status:
        query = query.filter(PhoneNumber.status == status)
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (PhoneNumber.phone_number.ilike(search_filter)) |
            (PhoneNumber.notes.ilike(search_filter))
        )
    
    # Apply pagination
    phone_numbers = query.offset(skip).limit(limit).all()
    
    return [PhoneNumberResponse.from_orm(pn) for pn in phone_numbers]


@router.get("/{phone_number_id}", response_model=PhoneNumberResponse)
async def get_phone_number(
    phone_number_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific phone number by ID
    """
    phone_number = db.query(PhoneNumber).filter(PhoneNumber.id == phone_number_id).first()
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    return PhoneNumberResponse.from_orm(phone_number)


@router.put("/{phone_number_id}", response_model=PhoneNumberResponse)
async def update_phone_number(
    phone_number_id: int,
    update_data: PhoneNumberUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a phone number
    
    - **status**: New status for the phone number
    - **notes**: Updated notes
    """
    phone_number = db.query(PhoneNumber).filter(PhoneNumber.id == phone_number_id).first()
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Update fields
    if update_data.status is not None:
        phone_number.status = update_data.status
    
    if update_data.notes is not None:
        phone_number.notes = update_data.notes
    
    db.commit()
    db.refresh(phone_number)
    
    logger.info(f"Updated phone number {phone_number_id}: status={update_data.status}")
    
    return PhoneNumberResponse.from_orm(phone_number)


@router.delete("/{phone_number_id}")
async def delete_phone_number(
    phone_number_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a phone number
    """
    phone_number = db.query(PhoneNumber).filter(PhoneNumber.id == phone_number_id).first()
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    db.delete(phone_number)
    db.commit()
    
    logger.info(f"Deleted phone number {phone_number_id}")
    
    return {"message": "Phone number deleted successfully"}


@router.get("/stats/summary")
async def get_phone_number_stats(db: Session = Depends(get_db)):
    """
    Get summary statistics for phone numbers
    """
    total = db.query(PhoneNumber).count()
    pending = db.query(PhoneNumber).filter(PhoneNumber.status == "pending").count()
    processing = db.query(PhoneNumber).filter(PhoneNumber.status == "processing").count()
    completed = db.query(PhoneNumber).filter(PhoneNumber.status == "completed").count()
    failed = db.query(PhoneNumber).filter(PhoneNumber.status == "failed").count()
    cancelled = db.query(PhoneNumber).filter(PhoneNumber.status == "cancelled").count()
    
    return {
        "total": total,
        "pending": pending,
        "processing": processing,
        "completed": completed,
        "failed": failed,
        "cancelled": cancelled,
        "success_rate": (completed / total * 100) if total > 0 else 0
    }



