from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional
from datetime import datetime, timedelta
from loguru import logger

from ...core.database import get_db
from ...core.models import (
    PhoneNumber, CRMStatus, Consent, RemovalStats, ProcessingTimeStats, ErrorRateStats
)

router = APIRouter()


@router.get("/removal-stats", response_model=RemovalStats)
async def get_removal_stats(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Get removal statistics for the specified date range
    """
    query = db.query(PhoneNumber)
    
    # Apply date filters if provided
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(PhoneNumber.created_at >= start_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use YYYY-MM-DD"
            )
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(PhoneNumber.created_at < end_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use YYYY-MM-DD"
            )
    
    # Get counts
    total_processed = query.count()
    successful_removals = query.filter(PhoneNumber.status == "completed").count()
    failed_removals = query.filter(PhoneNumber.status == "failed").count()
    pending_removals = query.filter(PhoneNumber.status == "pending").count()
    
    # Calculate success rate
    success_rate = (successful_removals / total_processed * 100) if total_processed > 0 else 0
    
    # Calculate average processing time (for completed removals)
    completed_phones = query.filter(PhoneNumber.status == "completed").all()
    total_processing_time = 0
    count_with_processing_time = 0
    
    for phone in completed_phones:
        # Get the latest CRM status for this phone
        latest_crm_status = db.query(CRMStatus).filter(
            CRMStatus.phone_number_id == phone.id,
            CRMStatus.status == "completed"
        ).order_by(CRMStatus.processed_at.desc()).first()
        
        if latest_crm_status and latest_crm_status.processed_at and phone.created_at:
            processing_time = (latest_crm_status.processed_at - phone.created_at).total_seconds()
            total_processing_time += processing_time
            count_with_processing_time += 1
    
    average_processing_time = (total_processing_time / count_with_processing_time) if count_with_processing_time > 0 else 0
    
    return RemovalStats(
        total_processed=total_processed,
        successful_removals=successful_removals,
        failed_removals=failed_removals,
        pending_removals=pending_removals,
        success_rate=round(success_rate, 2),
        average_processing_time=round(average_processing_time, 2)
    )


@router.get("/processing-times", response_model=List[ProcessingTimeStats])
async def get_processing_time_stats(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Get processing time statistics by CRM system
    """
    # Get all CRM systems
    crm_systems = db.query(CRMStatus.crm_system).distinct().all()
    crm_systems = [system[0] for system in crm_systems]
    
    stats = []
    
    for crm_system in crm_systems:
        # Build query for this CRM system
        query = db.query(CRMStatus).filter(
            CRMStatus.crm_system == crm_system,
            CRMStatus.status == "completed",
            CRMStatus.processed_at.isnot(None)
        )
        
        # Apply date filters if provided
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                query = query.filter(CRMStatus.processed_at >= start_dt)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid start_date format. Use YYYY-MM-DD"
                )
        
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                query = query.filter(CRMStatus.processed_at < end_dt)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid end_date format. Use YYYY-MM-DD"
                )
        
        completed_statuses = query.all()
        
        if not completed_statuses:
            stats.append(ProcessingTimeStats(
                crm_system=crm_system,
                average_time=0,
                min_time=0,
                max_time=0,
                total_requests=0
            ))
            continue
        
        # Calculate processing times
        processing_times = []
        for status in completed_statuses:
            phone = db.query(PhoneNumber).filter(PhoneNumber.id == status.phone_number_id).first()
            if phone and phone.created_at:
                processing_time = (status.processed_at - phone.created_at).total_seconds()
                processing_times.append(processing_time)
        
        if processing_times:
            avg_time = sum(processing_times) / len(processing_times)
            min_time = min(processing_times)
            max_time = max(processing_times)
        else:
            avg_time = min_time = max_time = 0
        
        stats.append(ProcessingTimeStats(
            crm_system=crm_system,
            average_time=round(avg_time, 2),
            min_time=round(min_time, 2),
            max_time=round(max_time, 2),
            total_requests=len(completed_statuses)
        ))
    
    return stats


@router.get("/error-rates", response_model=List[ErrorRateStats])
async def get_error_rate_stats(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Get error rate statistics by CRM system
    """
    # Get all CRM systems
    crm_systems = db.query(CRMStatus.crm_system).distinct().all()
    crm_systems = [system[0] for system in crm_systems]
    
    stats = []
    
    for crm_system in crm_systems:
        # Build query for this CRM system
        query = db.query(CRMStatus).filter(CRMStatus.crm_system == crm_system)
        
        # Apply date filters if provided
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                query = query.filter(CRMStatus.created_at >= start_dt)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid start_date format. Use YYYY-MM-DD"
                )
        
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                query = query.filter(CRMStatus.created_at < end_dt)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid end_date format. Use YYYY-MM-DD"
                )
        
        total_requests = query.count()
        error_count = query.filter(CRMStatus.status == "failed").count()
        
        # Get common error messages
        error_messages = db.query(CRMStatus.error_message).filter(
            CRMStatus.crm_system == crm_system,
            CRMStatus.status == "failed",
            CRMStatus.error_message.isnot(None)
        ).all()
        
        # Count error occurrences
        error_counts = {}
        for msg in error_messages:
            if msg[0]:
                error_counts[msg[0]] = error_counts.get(msg[0], 0) + 1
        
        # Get top 5 most common errors
        common_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        common_errors = [error[0] for error in common_errors]
        
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
        
        stats.append(ErrorRateStats(
            crm_system=crm_system,
            error_count=error_count,
            total_requests=total_requests,
            error_rate=round(error_rate, 2),
            common_errors=common_errors
        ))
    
    return stats


@router.get("/daily-summary")
async def get_daily_summary(
    date: str = Query(..., description="Date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Get daily summary for a specific date
    """
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
        next_date = target_date + timedelta(days=1)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD"
        )
    
    # Phone numbers added on this date
    phones_added = db.query(PhoneNumber).filter(
        PhoneNumber.created_at >= target_date,
        PhoneNumber.created_at < next_date
    ).count()
    
    # Phone numbers completed on this date
    phones_completed = db.query(PhoneNumber).filter(
        PhoneNumber.status == "completed",
        PhoneNumber.updated_at >= target_date,
        PhoneNumber.updated_at < next_date
    ).count()
    
    # CRM operations on this date
    crm_operations = db.query(CRMStatus).filter(
        CRMStatus.created_at >= target_date,
        CRMStatus.created_at < next_date
    ).count()
    
    # CRM operations by status
    crm_completed = db.query(CRMStatus).filter(
        CRMStatus.status == "completed",
        CRMStatus.processed_at >= target_date,
        CRMStatus.processed_at < next_date
    ).count()
    
    crm_failed = db.query(CRMStatus).filter(
        CRMStatus.status == "failed",
        CRMStatus.processed_at >= target_date,
        CRMStatus.processed_at < next_date
    ).count()
    
    # Consent records created on this date
    consents_created = db.query(Consent).filter(
        Consent.created_at >= target_date,
        Consent.created_at < next_date
    ).count()
    
    return {
        "date": date,
        "phone_numbers": {
            "added": phones_added,
            "completed": phones_completed
        },
        "crm_operations": {
            "total": crm_operations,
            "completed": crm_completed,
            "failed": crm_failed,
            "success_rate": (crm_completed / (crm_completed + crm_failed) * 100) if (crm_completed + crm_failed) > 0 else 0
        },
        "consents": {
            "created": consents_created
        }
    }


@router.get("/export/phone-numbers")
async def export_phone_numbers(
    format: str = Query("csv", description="Export format (csv, json)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """
    Export phone numbers data
    """
    query = db.query(PhoneNumber)
    
    # Apply filters
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(PhoneNumber.created_at >= start_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use YYYY-MM-DD"
            )
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(PhoneNumber.created_at < end_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use YYYY-MM-DD"
            )
    
    if status:
        query = query.filter(PhoneNumber.status == status)
    
    phone_numbers = query.all()
    
    if format.lower() == "json":
        return {
            "phone_numbers": [
                {
                    "id": pn.id,
                    "phone_number": pn.phone_number,
                    "status": pn.status,
                    "notes": pn.notes,
                    "created_at": pn.created_at.isoformat(),
                    "updated_at": pn.updated_at.isoformat()
                }
                for pn in phone_numbers
            ]
        }
    elif format.lower() == "csv":
        # For CSV, you would typically return a file response
        # This is a simplified version
        csv_data = "id,phone_number,status,notes,created_at,updated_at\n"
        for pn in phone_numbers:
            csv_data += f"{pn.id},{pn.phone_number},{pn.status},{pn.notes or ''},{pn.created_at},{pn.updated_at}\n"
        
        return {"csv_data": csv_data}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported format. Use 'csv' or 'json'"
        )





