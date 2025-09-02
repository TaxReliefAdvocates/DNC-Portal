from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from loguru import logger

from ...core.database import get_db
from ...core.models import (
    CRMStatus, CRMStatusCreate, CRMStatusUpdate, CRMStatusResponse,
    PhoneNumber
)
from ...core.crm_clients.base import BaseCRMClient
from ...core.crm_clients.trackdrive import TrackDriveClient
from ...core.crm_clients.everysource import EverySourceClient

router = APIRouter()


def get_crm_client(crm_system: str) -> BaseCRMClient:
    """Get CRM client based on system name"""
    if crm_system == "trackdrive":
        return TrackDriveClient()
    elif crm_system == "everysource":
        return EverySourceClient()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported CRM system: {crm_system}"
        )


@router.post("/remove-number")
async def remove_number_from_crm(
    phone_number_id: int,
    crm_system: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Remove a phone number from a specific CRM system
    
    - **phone_number_id**: ID of the phone number to remove
    - **crm_system**: CRM system name (trackdrive, everysource, etc.)
    """
    # Get phone number
    phone_number = db.query(PhoneNumber).filter(PhoneNumber.id == phone_number_id).first()
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Check if CRM status already exists
    existing_status = db.query(CRMStatus).filter(
        CRMStatus.phone_number_id == phone_number_id,
        CRMStatus.crm_system == crm_system
    ).first()
    
    if existing_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phone number already has status for {crm_system}"
        )
    
    # Create CRM status record
    crm_status = CRMStatus(
        phone_number_id=phone_number_id,
        crm_system=crm_system,
        status="pending"
    )
    db.add(crm_status)
    db.commit()
    db.refresh(crm_status)
    
    # Start background task for CRM removal
    background_tasks.add_task(
        process_crm_removal,
        crm_status.id,
        phone_number.phone_number,
        crm_system
    )
    
    logger.info(f"Started CRM removal for phone {phone_number.phone_number} in {crm_system}")
    
    return {
        "message": f"Removal request submitted for {crm_system}",
        "crm_status_id": crm_status.id,
        "status": "pending"
    }


async def process_crm_removal(crm_status_id: int, phone_number: str, crm_system: str):
    """Background task to process CRM removal"""
    from ...core.database import SessionLocal
    
    db = SessionLocal()
    try:
        # Get CRM status record
        crm_status = db.query(CRMStatus).filter(CRMStatus.id == crm_status_id).first()
        if not crm_status:
            logger.error(f"CRM status {crm_status_id} not found")
            return
        
        # Update status to processing
        crm_status.status = "processing"
        db.commit()
        
        # Get CRM client
        crm_client = get_crm_client(crm_system)
        
        # Attempt removal
        try:
            result = await crm_client.remove_phone_number(phone_number)
            
            # Update status based on result
            crm_status.status = "completed"
            crm_status.response_data = result
            crm_status.processed_at = datetime.utcnow()
            
            logger.info(f"Successfully removed {phone_number} from {crm_system}")
            
        except Exception as e:
            # Handle failure
            crm_status.status = "failed"
            crm_status.error_message = str(e)
            crm_status.retry_count += 1
            crm_status.processed_at = datetime.utcnow()
            
            logger.error(f"Failed to remove {phone_number} from {crm_system}: {e}")
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Error in CRM removal task: {e}")
    finally:
        db.close()


@router.get("/status/{phone_number}", response_model=List[CRMStatusResponse])
async def get_crm_status_by_phone(
    phone_number: str,
    db: Session = Depends(get_db)
):
    """
    Get CRM status for a specific phone number
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
    
    # Get all CRM statuses for this phone number
    crm_statuses = db.query(CRMStatus).filter(
        CRMStatus.phone_number_id == phone_record.id
    ).all()
    
    return [CRMStatusResponse.from_orm(status) for status in crm_statuses]


@router.get("/statuses", response_model=List[CRMStatusResponse])
async def get_all_crm_statuses(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    crm_system: Optional[str] = Query(None, description="Filter by CRM system"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """
    Get all CRM statuses with optional filtering
    """
    query = db.query(CRMStatus)
    
    # Apply filters
    if crm_system:
        query = query.filter(CRMStatus.crm_system == crm_system)
    
    if status:
        query = query.filter(CRMStatus.status == status)
    
    # Apply pagination
    crm_statuses = query.offset(skip).limit(limit).all()
    
    return [CRMStatusResponse.from_orm(status) for status in crm_statuses]


@router.post("/retry-removal")
async def retry_crm_removal(
    crm_status_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Retry a failed CRM removal
    """
    # Get CRM status record
    crm_status = db.query(CRMStatus).filter(CRMStatus.id == crm_status_id).first()
    if not crm_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CRM status not found"
        )
    
    if crm_status.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only retry failed removals"
        )
    
    # Get phone number
    phone_number = db.query(PhoneNumber).filter(
        PhoneNumber.id == crm_status.phone_number_id
    ).first()
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Reset status for retry
    crm_status.status = "pending"
    crm_status.error_message = None
    db.commit()
    
    # Start background task for retry
    background_tasks.add_task(
        process_crm_removal,
        crm_status.id,
        phone_number.phone_number,
        crm_status.crm_system
    )
    
    logger.info(f"Retrying CRM removal for {phone_number.phone_number} in {crm_status.crm_system}")
    
    return {
        "message": "Retry request submitted",
        "crm_status_id": crm_status.id,
        "status": "pending"
    }


@router.get("/stats/summary")
async def get_crm_stats(db: Session = Depends(get_db)):
    """
    Get summary statistics for CRM operations
    """
    # Get stats by CRM system
    stats = {}
    
    for crm_system in ["trackdrive", "everysource", "other"]:
        total = db.query(CRMStatus).filter(CRMStatus.crm_system == crm_system).count()
        pending = db.query(CRMStatus).filter(
            CRMStatus.crm_system == crm_system,
            CRMStatus.status == "pending"
        ).count()
        processing = db.query(CRMStatus).filter(
            CRMStatus.crm_system == crm_system,
            CRMStatus.status == "processing"
        ).count()
        completed = db.query(CRMStatus).filter(
            CRMStatus.crm_system == crm_system,
            CRMStatus.status == "completed"
        ).count()
        failed = db.query(CRMStatus).filter(
            CRMStatus.crm_system == crm_system,
            CRMStatus.status == "failed"
        ).count()
        
        stats[crm_system] = {
            "total": total,
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "success_rate": (completed / total * 100) if total > 0 else 0
        }
    
    return stats



