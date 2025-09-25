"""
FreeDNCList.com API Replication
Replicates the exact workflow of FreeDNCList.com for DNC checking
"""
import os
import csv
import io
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from fastapi import APIRouter, File, Form, HTTPException, status, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from loguru import logger

from do_not_call.core.database import get_db
from do_not_call.core.dnc_service import dnc_service
from do_not_call.core.cookie_fetcher import fetch_freednclist_phpsessid
from do_not_call.core.tps_database import tps_database
from do_not_call.core.tps_api import tps_api
from do_not_call.config import settings

router = APIRouter()

# Create uploads directory (configurable via env UPLOADS_DIR) if it doesn't exist
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "uploads"))
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks"""
    # Remove any path separators and dangerous characters
    safe_name = "".join(c for c in filename if c.isalnum() or c in "._-")
    return safe_name[:100]  # Limit length

def generate_unique_filename(original_filename: str) -> str:
    """Generate unique filename for processed CSV"""
    base_name = Path(original_filename).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"{base_name}_checked_{timestamp}_{unique_id}.csv"

async def process_csv_with_dnc(
    csv_content: str,
    column_index: int,
    db: Session
) -> List[List[str]]:
    """
    Process CSV content and add DNC status column
    
    Args:
        csv_content: Raw CSV content as string
        column_index: Column index containing phone numbers
        db: Database session
        
    Returns:
        List of rows with DNC status added
    """
    try:
        # Parse CSV content
        csv_reader = csv.reader(io.StringIO(csv_content))
        rows = list(csv_reader)
        
        if not rows:
            raise ValueError("CSV file is empty")
        
        # Validate column index
        if column_index >= len(rows[0]):
            raise ValueError(f"Column index {column_index} is out of range. File has {len(rows[0])} columns.")
        
        # Add DNC status header
        header = rows[0] + ["DNC_Status"]
        processed_rows = [header]
        
        # Process each data row
        for row_num, row in enumerate(rows[1:], 1):
            if len(row) <= column_index:
                # Row doesn't have enough columns, add empty DNC status
                processed_rows.append(row + ["INVALID_ROW"])
                continue
            
            try:
                phone_raw = row[column_index].strip()
                
                # Check DNC status using our service
                dnc_status = await dnc_service.check_federal_dnc(phone_raw)
                
                # Determine DNC status for CSV - using the exact format expected
                if dnc_status["is_dnc"]:
                    dnc_csv_status = "Yes - On DNC List"
                elif dnc_status["status"] == "invalid":
                    dnc_csv_status = "INVALID_FORMAT"
                elif dnc_status["status"] == "error":
                    dnc_csv_status = "CHECK_ERROR"
                else:
                    dnc_csv_status = "No - Not on DNC"
                
                # Add DNC status to row
                processed_rows.append(row + [dnc_csv_status])
                
            except Exception as e:
                logger.error(f"Error processing row {row_num}: {e}")
                processed_rows.append(row + ["PROCESSING_ERROR"])
        
        return processed_rows
        
    except Exception as e:
        logger.error(f"Error processing CSV: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing CSV: {str(e)}"
        )

@router.post("/process")
async def process_dnc_csv(
    file: bytes = File(..., description="CSV file to process"),
    column_index: str = Form("0", description="Column index containing phone numbers (default: 0)"),
    format: str = Form("json", description="Output format (default: json)"),
    db: Session = Depends(get_db)
):
    """
    Process CSV file against DNC database - replicates FreeDNCList.com process.php
    
    Args:
        file: CSV file content
        column_index: Column index for phone numbers (0-based)
        format: Output format (json)
        db: Database session
        
    Returns:
        JSON response with file path for download
    """
    try:
        # Validate column index
        try:
            col_idx = int(column_index)
            if col_idx < 0:
                raise ValueError("Column index must be non-negative")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Column index must be a valid integer"
            )
        
        # Decode file content
        try:
            csv_content = file.decode('utf-8')
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be UTF-8 encoded"
            )
        
        # Process CSV with DNC checking
        processed_rows = await process_csv_with_dnc(csv_content, col_idx, db)
        
        # Generate unique filename
        original_filename = "contacts_DNC.csv"  # Default name like FreeDNCList.com
        unique_filename = generate_unique_filename(original_filename)
        file_path = UPLOADS_DIR / unique_filename
        
        # Write processed CSV to file
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerows(processed_rows)
        
        # Generate processing ID for tracking
        processing_id = str(uuid.uuid4())
        
        # Return response exactly like FreeDNCList.com
        result = {
            "success": True,
            "file": f"/uploads/{unique_filename}",
            "processing_id": processing_id
        }
        
        logger.info(f"Successfully processed CSV: {len(processed_rows)-1} records, saved to {file_path}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing DNC CSV: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/uploads/{filename}")
async def download_processed_file(filename: str):
    """
    Download processed CSV file - replicates FreeDNCList.com file download
    
    Args:
        filename: Name of the processed file to download
        
    Returns:
        CSV file for download
    """
    try:
        # Sanitize filename to prevent path traversal
        safe_filename = sanitize_filename(filename)
        file_path = UPLOADS_DIR / safe_filename
        
        # Check if file exists
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Check if file is actually in uploads directory (security check)
        try:
            file_path.resolve().relative_to(UPLOADS_DIR.resolve())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Return file for download
        return FileResponse(
            path=file_path,
            filename=safe_filename,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={safe_filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file {filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading file: {str(e)}"
        )

@router.get("/check")
async def check_status():
    """
    Check endpoint - replicates FreeDNCList.com check.php
    Returns basic status information
    """
    return {
        "status": "ready",
        "message": "DNC processing service is available",
        "timestamp": datetime.now().isoformat()
    }

@router.post("/cookies/refresh")
async def refresh_freednclist_cookies():
    """Refresh FreeDNCList PHPSESSID using Playwright."""
    try:
        session_id = await fetch_freednclist_phpsessid()
        if session_id:
            # update the global service cache
            dnc_service.freednclist_session = session_id
            return {
                "success": True,
                "cookie": "PHPSESSID",
                "value_preview": session_id[:6] + "...",
                "updated_at": datetime.now().isoformat()
            }
        return {
            "success": False,
            "message": "Could not fetch PHPSESSID"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cookie refresh error: {str(e)}"
        )

@router.post("/check_number")
async def check_single_number(
    phone_data: dict,
    db: Session = Depends(get_db)
):
    """
    Check single phone number against DNC - replicates FreeDNCList.com check_number.php
    
    Args:
        phone_data: JSON with phone_number field
        db: Database session
        
    Returns:
        DNC status for the phone number
    """
    try:
        phone_number = phone_data.get("phone_number")
        if not phone_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="phone_number field is required"
            )
        
        # Check DNC status using our service
        dnc_status = await dnc_service.check_federal_dnc(phone_number)
        
        # Return response in the format expected by frontend
        return {
            "success": True,
            "phone_number": phone_number,
            "is_dnc": dnc_status["is_dnc"],
            "dnc_source": dnc_status["dnc_source"],
            "status": dnc_status["status"],
            "notes": dnc_status["notes"],
            "checked_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking phone number {phone_data}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking phone number: {str(e)}"
        )

@router.post("/check_batch")
async def check_batch_numbers(
    phone_data: dict,
    db: Session = Depends(get_db)
):
    """
    Check multiple phone numbers against DNC - batch processing
    
    Args:
        phone_data: JSON with phone_numbers array field
        db: Database session
        
    Returns:
        DNC status for all phone numbers
    """
    try:
        phone_numbers = phone_data.get("phone_numbers")
        if not phone_numbers or not isinstance(phone_numbers, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="phone_numbers field must be an array"
            )
        
        if len(phone_numbers) > 1000:  # Limit batch size
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 1000 phone numbers per batch"
            )
        
        # Process all phone numbers asynchronously
        results = []
        for phone_number in phone_numbers:
            try:
                dnc_status = await dnc_service.check_federal_dnc(phone_number)
                results.append({
                    "phone_number": phone_number,
                    "is_dnc": dnc_status["is_dnc"],
                    "dnc_source": dnc_status["dnc_source"],
                    "status": dnc_status["status"],
                    "notes": dnc_status["notes"]
                })
            except Exception as e:
                logger.error(f"Error checking phone number {phone_number}: {e}")
                results.append({
                    "phone_number": phone_number,
                    "is_dnc": False,
                    "dnc_source": "error",
                    "status": "error",
                    "notes": f"Error: {str(e)}"
                })
        
        # Return batch results
        return {
            "success": True,
            "total_checked": len(results),
            "dnc_matches": len([r for r in results if r["is_dnc"]]),
            "safe_to_call": len([r for r in results if not r["is_dnc"]]),
            "results": results,
            "checked_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch DNC check: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in batch DNC check: {str(e)}"
        )

@router.post("/check_tps_database", include_in_schema=False)
async def check_tps_database_dnc(
    request_data: dict,
    db: Session = Depends(get_db)
):
    """
    Check phone numbers from TPS2 database against DNC lists
    
    Args:
        request_data: JSON with limit field (optional, default: 1000)
        db: Database session
        
    Returns:
        DNC status for all phone numbers from TPS2 database
    """
    try:
        limit = request_data.get("limit", 1000)
        
        # Validate limit
        if not isinstance(limit, int) or limit < 1 or limit > 10000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit must be an integer between 1 and 10000"
            )
        
        logger.info(f"Starting TPS2 database DNC check for up to {limit} phone numbers")
        
        # Get phone numbers from TPS2 database
        phone_records = await tps_database.get_phone_numbers(limit)
        
        if not phone_records:
            return {
                "success": True,
                "message": "No phone numbers found in TPS2 database",
                "total_checked": 0,
                "dnc_matches": 0,
                "safe_to_call": 0,
                "results": [],
                "checked_at": datetime.now().isoformat()
            }
        
        logger.info(f"Retrieved {len(phone_records)} phone numbers from TPS2 database")
        
        # Process each phone number through DNC checking
        results = []
        for record in phone_records:
            try:
                phone_number = record.get("PhoneNumber", "")
                if not phone_number:
                    continue
                
                # Check DNC status using our service
                dnc_status = await dnc_service.check_federal_dnc(phone_number)
                
                # Add DNC status to the record
                result = {
                    **record,
                    "is_dnc": dnc_status["is_dnc"],
                    "dnc_source": dnc_status["dnc_source"],
                    "dnc_status": dnc_status["status"],
                    "dnc_notes": dnc_status["notes"]
                }
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error checking DNC for phone number {record.get('PhoneNumber', 'unknown')}: {e}")
                result = {
                    **record,
                    "is_dnc": False,
                    "dnc_source": "error",
                    "dnc_status": "error",
                    "dnc_notes": f"Error: {str(e)}"
                }
                results.append(result)
        
        # Calculate summary statistics
        dnc_matches = len([r for r in results if r["is_dnc"]])
        safe_to_call = len([r for r in results if not r["is_dnc"]])
        
        logger.info(f"TPS2 database DNC check complete: {len(results)} checked, {dnc_matches} DNC matches")
        
        return {
            "success": True,
            "message": f"Successfully checked {len(results)} phone numbers from TPS2 database",
            "total_checked": len(results),
            "dnc_matches": dnc_matches,
            "safe_to_call": safe_to_call,
            "results": results,
            "checked_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in TPS2 database DNC check: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in TPS2 database DNC check: {str(e)}"
        )

@router.get("/test_tps_connection")
async def test_tps_connection():
    """
    Test connection to TPS2 database
    """
    try:
        is_connected = await tps_database.test_connection()
        return {
            "success": is_connected,
            "message": "TPS2 database connection test",
            "connected": is_connected,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"TPS2 connection test failed: {e}")
        return {
            "success": False,
            "message": f"TPS2 database connection test failed: {str(e)}",
            "connected": False,
            "timestamp": datetime.now().isoformat()
        }

@router.get("/status/{processing_id}")
async def get_processing_status(processing_id: str):
    """
    Get processing status for a given processing ID
    
    Args:
        processing_id: The processing ID returned from the process endpoint
        
    Returns:
        Processing status information
    """
    # This is a placeholder - in a real implementation you might track processing status
    # For now, just return a basic status
    return {
        "processing_id": processing_id,
        "status": "completed",
        "message": "Processing completed successfully"
    }

@router.post("/cases_by_phone", include_in_schema=False)
async def cases_by_phone(request_data: dict):
    """
    Return all cases for a given phone number across TPS2 phone fields.

    Args:
        request_data: { "phone_number": "..." }
    Returns:
        List of case entries with CaseID, CreatedDate, LastModifiedDate, StatusID, StatusName, PhoneType
    """
    try:
        phone_number = request_data.get("phone_number")
        if not phone_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="phone_number is required"
            )

        # 1) Use TPS API to find cases by phone, unless an initial_case_id is provided
        initial_case_id = request_data.get("case_id")
        found = []
        if initial_case_id:
            found = [{"CaseID": initial_case_id, "CreatedDate": None, "StatusID": None, "CellPhone": phone_number}]
        else:
            found = await tps_api.find_cases_by_phone(phone_number)
        cases: List[Dict[str, Any]] = []

        # 2) For each CaseID, fetch detailed info to get ModifiedDate, StatusName
        # Prefer configured key, fall back to request override if provided
        api_key = request_data.get("apikey") or settings.TPS_API_KEY
        for entry in found:
            case_id = entry.get("CaseID")
            if not case_id:
                continue
            detail = await tps_api.get_case_info(int(case_id), api_key=api_key)
            created_date = (detail or {}).get("CreatedDate") or entry.get("CreatedDate")
            status_id = entry.get("StatusID") or (detail or {}).get("StatusID")
            cases.append({
                "CaseID": case_id,
                "CreatedDate": created_date,
                "StatusID": status_id,
                "StatusName": (detail or {}).get("StatusName"),
                "LastModifiedDate": (detail or {}).get("ModifiedDate"),
                "PhoneType": _infer_phone_type(entry, phone_number)
            })

        return {
            "success": True,
            "phone_number": phone_number,
            "count": len(cases),
            "cases": cases,
            "queried_at": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching cases for phone {request_data}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching cases: {str(e)}"
        )

def _infer_phone_type(entry: Dict[str, Any], target: str) -> str:
    for key in ("CellPhone", "HomePhone", "WorkPhone"):
        value = entry.get(key) or ""
        if value == target:
            return key
    return "Unknown"

@router.post("/run_automation")
async def run_dnc_automation(request_data: dict):
    """
    Stub endpoint to trigger DNC automation across CRMs for a phone number.
    Currently returns a placeholder response; integration hooks to Convoso, Ytel,
    RingCentral, and Genesys will be wired later.
    """
    try:
        phone_number = request_data.get("phone_number")
        if not phone_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="phone_number is required"
            )

        # Placeholder: return an accepted response for now
        return {
            "success": True,
            "message": "DNC automation initiated (stub)",
            "phone_number": phone_number,
            "started_at": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating automation for {request_data}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Automation start failed: {str(e)}"
        )
