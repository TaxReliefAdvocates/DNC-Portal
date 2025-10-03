from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from loguru import logger

from ...core.database import get_db
from ...core.auth import Principal, require_role
from ...core.models import SearchHistory, SearchHistoryResponse

router = APIRouter()


@router.get("/recent", response_model=List[SearchHistoryResponse])
async def get_recent_searches(
    limit: int = 10,
    db: Session = Depends(get_db),
    principal: Principal = Depends(Principal)
):
    """Get recent search history for the current user"""
    require_role("owner", "admin", "superadmin")(principal)
    
    # Get user ID from principal
    user_id = getattr(principal, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in principal")
    
    # Get recent searches for this user
    searches = db.query(SearchHistory).filter(
        SearchHistory.user_id == user_id
    ).order_by(
        SearchHistory.created_at.desc()
    ).limit(limit).all()
    
    return searches


@router.post("/save")
async def save_search(
    phone_number: str,
    search_results: dict,
    db: Session = Depends(get_db),
    principal: Principal = Depends(Principal)
):
    """Save a search to history"""
    require_role("owner", "admin", "superadmin")(principal)
    
    # Get user ID and organization ID from principal
    user_id = getattr(principal, 'user_id', None)
    organization_id = getattr(principal, 'organization_id', None)
    
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in principal")
    
    # Create search history entry
    search_entry = SearchHistory(
        user_id=user_id,
        organization_id=organization_id,
        phone_number=phone_number,
        search_results=search_results
    )
    
    db.add(search_entry)
    db.commit()
    db.refresh(search_entry)
    
    logger.info(f"Saved search history for user {user_id}: {phone_number}")
    
    return {"success": True, "message": "Search saved to history"}
