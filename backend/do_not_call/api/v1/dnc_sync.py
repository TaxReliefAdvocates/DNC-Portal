from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger

from ..core.database import get_db
from ..core.models import MasterDNCEntry, DNCSyncStatus, DNCSyncJob, MasterDNCEntryResponse, DNCSyncStatusResponse, DNCSyncJobResponse
from ..core.auth import Principal, require_role
from .providers.convoso import list_all_dnc
from .providers.ringcentral import add_to_dnc as rc_add_to_dnc
from .providers.genesys import add_to_dnc as genesys_add_to_dnc
from .providers.ytel import add_to_dnc as ytel_add_to_dnc
from .providers.logics import update_case as logics_update_case
from .common import AddToDNCRequest, SearchByPhoneRequest, LogicsUpdateCaseRequest

router = APIRouter()


@router.get("/master-dnc", response_model=List[MasterDNCEntryResponse])
@require_role(["owner", "admin", "superadmin"])
async def get_master_dnc_list(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    principal: Principal = Depends(Principal)
):
    """Get the master DNC list from PostgreSQL"""
    entries = db.query(MasterDNCEntry).offset(skip).limit(limit).all()
    return entries


@router.get("/sync-status", response_model=List[DNCSyncStatusResponse])
@require_role(["owner", "admin", "superadmin"])
async def get_sync_status(
    provider: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    principal: Principal = Depends(Principal)
):
    """Get DNC sync status across providers"""
    query = db.query(DNCSyncStatus)
    
    if provider:
        query = query.filter(DNCSyncStatus.provider == provider)
    if status:
        query = query.filter(DNCSyncStatus.status == status)
    
    entries = query.offset(skip).limit(limit).all()
    return entries


@router.get("/sync-jobs", response_model=List[DNCSyncJobResponse])
@require_role(["owner", "admin", "superadmin"])
async def get_sync_jobs(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    principal: Principal = Depends(Principal)
):
    """Get DNC sync job history"""
    jobs = db.query(DNCSyncJob).order_by(desc(DNCSyncJob.created_at)).offset(skip).limit(limit).all()
    return jobs


@router.post("/sync-from-convoso")
@require_role(["owner", "admin", "superadmin"])
async def sync_from_convoso(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    principal: Principal = Depends(Principal)
):
    """Sync DNC list from Convoso to master database"""
    
    # Create sync job record
    sync_job = DNCSyncJob(
        job_type="full_sync",
        status="running",
        started_at=datetime.utcnow()
    )
    db.add(sync_job)
    db.commit()
    db.refresh(sync_job)
    
    # Start background task
    background_tasks.add_task(perform_convoso_sync, sync_job.id, db)
    
    return {"message": "DNC sync from Convoso started", "job_id": sync_job.id}


async def perform_convoso_sync(job_id: int, db: Session):
    """Background task to sync DNC list from Convoso"""
    try:
        # Get the sync job
        sync_job = db.query(DNCSyncJob).filter(DNCSyncJob.id == job_id).first()
        if not sync_job:
            logger.error(f"Sync job {job_id} not found")
            return
        
        # Get DNC list from Convoso
        logger.info("Fetching DNC list from Convoso...")
        from .common import ListAllDNCRequest
        convoso_response = await list_all_dnc(ListAllDNCRequest())
        
        if not convoso_response.success:
            sync_job.status = "failed"
            sync_job.error_message = "Failed to fetch DNC list from Convoso"
            sync_job.completed_at = datetime.utcnow()
            db.commit()
            return
        
        dnc_numbers = convoso_response.data.get("dnc_numbers", [])
        sync_job.total_entries = len(dnc_numbers)
        db.commit()
        
        logger.info(f"Processing {len(dnc_numbers)} DNC entries from Convoso...")
        
        # Process each DNC entry
        for entry_data in dnc_numbers:
            try:
                phone_number = entry_data["phone_number"]
                
                # Check if entry already exists
                existing_entry = db.query(MasterDNCEntry).filter(
                    MasterDNCEntry.phone_number == phone_number
                ).first()
                
                if existing_entry:
                    # Update existing entry
                    existing_entry.convoso_lead_id = entry_data.get("lead_id")
                    existing_entry.first_name = entry_data.get("first_name")
                    existing_entry.last_name = entry_data.get("last_name")
                    existing_entry.email = entry_data.get("email")
                    existing_entry.campaign_name = entry_data.get("campaign_name")
                    existing_entry.status = entry_data.get("status", "DNC")
                    existing_entry.last_synced_at = datetime.utcnow()
                    existing_entry.updated_at = datetime.utcnow()
                else:
                    # Create new entry
                    new_entry = MasterDNCEntry(
                        phone_number=phone_number,
                        convoso_lead_id=entry_data.get("lead_id"),
                        first_name=entry_data.get("first_name"),
                        last_name=entry_data.get("last_name"),
                        email=entry_data.get("email"),
                        campaign_name=entry_data.get("campaign_name"),
                        status=entry_data.get("status", "DNC"),
                        last_synced_at=datetime.utcnow()
                    )
                    db.add(new_entry)
                
                sync_job.processed_entries += 1
                
            except Exception as e:
                logger.error(f"Error processing DNC entry {entry_data}: {e}")
                sync_job.failed_syncs += 1
                continue
        
        # Commit all changes
        db.commit()
        
        # Mark job as completed
        sync_job.status = "completed"
        sync_job.completed_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"DNC sync from Convoso completed. Processed {sync_job.processed_entries} entries.")
        
    except Exception as e:
        logger.error(f"Error in Convoso sync job {job_id}: {e}")
        sync_job.status = "failed"
        sync_job.error_message = str(e)
        sync_job.completed_at = datetime.utcnow()
        db.commit()


@router.post("/sync-to-providers")
@require_role(["owner", "admin", "superadmin"])
async def sync_to_providers(
    providers: List[str] = ["ringcentral", "genesys", "ytel", "logics"],
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(Principal)
):
    """Sync DNC numbers to all providers"""
    
    # Create sync job record
    sync_job = DNCSyncJob(
        job_type="cross_provider_sync",
        status="running",
        started_at=datetime.utcnow()
    )
    db.add(sync_job)
    db.commit()
    db.refresh(sync_job)
    
    # Start background task
    background_tasks.add_task(perform_provider_sync, sync_job.id, providers, db)
    
    return {"message": "DNC sync to providers started", "job_id": sync_job.id}


async def perform_provider_sync(job_id: int, providers: List[str], db: Session):
    """Background task to sync DNC numbers to providers"""
    try:
        # Get the sync job
        sync_job = db.query(DNCSyncJob).filter(DNCSyncJob.id == job_id).first()
        if not sync_job:
            logger.error(f"Sync job {job_id} not found")
            return
        
        # Get all DNC entries that need syncing
        dnc_entries = db.query(MasterDNCEntry).all()
        sync_job.total_entries = len(dnc_entries)
        db.commit()
        
        logger.info(f"Syncing {len(dnc_entries)} DNC entries to {len(providers)} providers...")
        
        # Process each DNC entry
        for dnc_entry in dnc_entries:
            for provider in providers:
                try:
                    # Check if already synced to this provider
                    existing_sync = db.query(DNCSyncStatus).filter(
                        DNCSyncStatus.dnc_entry_id == dnc_entry.id,
                        DNCSyncStatus.provider == provider
                    ).first()
                    
                    if existing_sync and existing_sync.status == "synced":
                        sync_job.skipped_syncs += 1
                        continue
                    
                    # Create or update sync status
                    if not existing_sync:
                        sync_status = DNCSyncStatus(
                            dnc_entry_id=dnc_entry.id,
                            provider=provider,
                            status="pending"
                        )
                        db.add(sync_status)
                    else:
                        sync_status = existing_sync
                    
                    sync_status.last_attempt_at = datetime.utcnow()
                    sync_status.status = "pending"
                    db.commit()
                    
                    # Sync to provider
                    success = await sync_to_provider(dnc_entry.phone_number, provider, sync_status, db)
                    
                    if success:
                        sync_status.status = "synced"
                        sync_status.synced_at = datetime.utcnow()
                        sync_job.successful_syncs += 1
                    else:
                        sync_status.status = "failed"
                        sync_job.failed_syncs += 1
                    
                    sync_job.processed_entries += 1
                    db.commit()
                    
                except Exception as e:
                    logger.error(f"Error syncing {dnc_entry.phone_number} to {provider}: {e}")
                    if existing_sync:
                        existing_sync.status = "failed"
                        existing_sync.error_message = str(e)
                        db.commit()
                    sync_job.failed_syncs += 1
        
        # Mark job as completed
        sync_job.status = "completed"
        sync_job.completed_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Provider sync completed. Success: {sync_job.successful_syncs}, Failed: {sync_job.failed_syncs}")
        
    except Exception as e:
        logger.error(f"Error in provider sync job {job_id}: {e}")
        sync_job.status = "failed"
        sync_job.error_message = str(e)
        sync_job.completed_at = datetime.utcnow()
        db.commit()


async def sync_to_provider(phone_number: str, provider: str, sync_status: DNCSyncStatus, db: Session) -> bool:
    """Sync a single phone number to a specific provider"""
    try:
        if provider == "ringcentral":
            response = await rc_add_to_dnc(AddToDNCRequest(phone_number=phone_number))
        elif provider == "genesys":
            response = await genesys_add_to_dnc(AddToDNCRequest(phone_number=phone_number))
        elif provider == "ytel":
            response = await ytel_add_to_dnc(AddToDNCRequest(phone_number=phone_number))
        elif provider == "logics":
            # For Logics, we need to search for the case first
            from .providers.logics import search_by_phone
            search_response = await search_by_phone(SearchByPhoneRequest(phone_number=phone_number))
            if search_response.success and search_response.data.get("cases"):
                case_id = search_response.data["cases"][0]["CaseID"]
                response = await logics_update_case(LogicsUpdateCaseRequest(caseId=case_id, statusId=2))
            else:
                return False
        else:
            logger.error(f"Unknown provider: {provider}")
            return False
        
        if response and response.success:
            logger.info(f"Successfully synced {phone_number} to {provider}")
            return True
        else:
            logger.error(f"Failed to sync {phone_number} to {provider}: {response.message if response else 'No response'}")
            sync_status.error_message = response.message if response else "No response"
            return False
            
    except Exception as e:
        logger.error(f"Error syncing {phone_number} to {provider}: {e}")
        sync_status.error_message = str(e)
        return False


@router.get("/stats")
@require_role(["owner", "admin", "superadmin"])
async def get_sync_stats(
    db: Session = Depends(get_db),
    principal: Principal = Depends(Principal)
):
    """Get DNC sync statistics"""
    
    # Master DNC count
    total_dnc = db.query(MasterDNCEntry).count()
    
    # Sync status counts by provider
    provider_stats = {}
    providers = ["ringcentral", "genesys", "ytel", "logics"]
    
    for provider in providers:
        synced = db.query(DNCSyncStatus).filter(
            DNCSyncStatus.provider == provider,
            DNCSyncStatus.status == "synced"
        ).count()
        
        failed = db.query(DNCSyncStatus).filter(
            DNCSyncStatus.provider == provider,
            DNCSyncStatus.status == "failed"
        ).count()
        
        pending = db.query(DNCSyncStatus).filter(
            DNCSyncStatus.provider == provider,
            DNCSyncStatus.status == "pending"
        ).count()
        
        provider_stats[provider] = {
            "synced": synced,
            "failed": failed,
            "pending": pending,
            "total": synced + failed + pending
        }
    
    # Recent sync jobs
    recent_jobs = db.query(DNCSyncJob).order_by(desc(DNCSyncJob.created_at)).limit(5).all()
    
    return {
        "total_dnc_entries": total_dnc,
        "provider_stats": provider_stats,
        "recent_jobs": [
            {
                "id": job.id,
                "job_type": job.job_type,
                "status": job.status,
                "created_at": job.created_at,
                "completed_at": job.completed_at
            }
            for job in recent_jobs
        ]
    }
