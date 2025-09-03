from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import csv
import io
import re
from datetime import datetime
from loguru import logger

from ...core.database import get_db
from ...core.models import PhoneNumber
from ...config import settings

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
        raise ValueError(f"Invalid phone number format: {phone}. Must be 10 digits.")
    
    # Format as (XXX) XXX-XXXX
    return f"({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:]}"


def check_dnc_status(phone_number: str, db: Session) -> Dict[str, Any]:
    """Check if a phone number is on the DNC list"""
    # Check if phone number exists in our database
    existing_record = db.query(PhoneNumber).filter(
        PhoneNumber.phone_number == phone_number
    ).first()
    
    if existing_record:
        return {
            "is_dnc": True,
            "dnc_source": "internal_database",
            "status": existing_record.status,
            "notes": existing_record.notes
        }
    
    # TODO: Integrate with federal DNC API here
    # For now, return safe to call
    return {
        "is_dnc": False,
        "dnc_source": None,
        "status": "safe_to_call",
        "notes": None
    }


async def process_csv_chunk(
    csv_content: str, 
    column_index: int, 
    db: Session
) -> Dict[str, Any]:
    """Process a chunk of CSV content"""
    results = []
    total_records = 0
    dnc_matches = 0
    safe_to_call = 0
    
    try:
        # Parse CSV content
        csv_reader = csv.reader(io.StringIO(csv_content))
        
        for row_num, row in enumerate(csv_reader, 1):
            if not row or len(row) <= column_index:
                continue
                
            total_records += 1
            phone_raw = row[column_index].strip()
            
            try:
                # Validate and normalize phone number
                normalized_phone = validate_phone_number(phone_raw)
                
                # Check DNC status
                dnc_status = check_dnc_status(normalized_phone, db)
                
                # Create result record
                result_record = {
                    "original_data": row,
                    "phone_number": normalized_phone,
                    "is_dnc": dnc_status["is_dnc"],
                    "dnc_source": dnc_status["dnc_source"],
                    "status": dnc_status["status"],
                    "notes": dnc_status["notes"]
                }
                
                results.append(result_record)
                
                # Update counters
                if dnc_status["is_dnc"]:
                    dnc_matches += 1
                else:
                    safe_to_call += 1
                    
            except ValueError as e:
                # Invalid phone number
                results.append({
                    "original_data": row,
                    "phone_number": phone_raw,
                    "is_dnc": False,
                    "dnc_source": "invalid_format",
                    "status": "invalid",
                    "notes": str(e)
                })
                safe_to_call += 1
                
    except Exception as e:
        logger.error(f"Error processing CSV chunk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing CSV: {str(e)}"
        )
    
    return {
        "total_records": total_records,
        "dnc_matches": dnc_matches,
        "safe_to_call": safe_to_call,
        "data": results
    }


@router.post("/process-dnc")
async def process_dnc_csv(
    file: UploadFile = File(..., description="CSV file to process"),
    column_index: int = Form(0, description="Column index containing phone numbers (default: 0)"),
    db: Session = Depends(get_db)
):
    """
    Process a CSV file to check phone numbers against DNC lists
    
    - **file**: CSV file containing phone numbers
    - **column_index**: Column index containing phone numbers (0-based, default: 0)
    """
    # Validate file type
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported"
        )
    
    # Check file size
    if file.size and file.size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_FILE_SIZE / (1024*1024):.1f}MB"
        )
    
    # Validate column index
    if column_index < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Column index must be non-negative"
        )
    
    try:
        # Read file content
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        # Process CSV
        result = await process_csv_chunk(csv_content, column_index, db)
        
        # Add success flag
        result["success"] = True
        result["processed_at"] = datetime.utcnow().isoformat()
        result["filename"] = file.filename
        
        logger.info(f"Successfully processed CSV file {file.filename}: {result['total_records']} records, {result['dnc_matches']} DNC matches")
        
        return result
        
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File encoding error. Please ensure the file is UTF-8 encoded."
        )
    except Exception as e:
        logger.error(f"Error processing CSV file {file.filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )


@router.post("/process-dnc-batch")
async def process_dnc_csv_batch(
    file: UploadFile = File(..., description="Large CSV file to process in batches"),
    column_index: int = Form(0, description="Column index containing phone numbers (default: 0)"),
    batch_size: int = Form(100, description="Number of records to process per batch"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Process a large CSV file in batches for better performance
    
    - **file**: CSV file containing phone numbers
    - **column_index**: Column index containing phone numbers (0-based, default: 0)
    - **batch_size**: Number of records to process per batch (default: 100)
    """
    # Validate file type
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported"
        )
    
    # Check file size
    if file.size and file.size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_FILE_SIZE / (1024*1024):.1f}MB"
        )
    
    # Validate batch size
    if batch_size < 1 or batch_size > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch size must be between 1 and 1000"
        )
    
    try:
        # Read file content
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        # Count total rows first
        total_rows = sum(1 for _ in csv.reader(io.StringIO(csv_content)))
        
        # Process in batches
        csv_reader = csv.reader(io.StringIO(csv_content))
        all_results = []
        total_records = 0
        dnc_matches = 0
        safe_to_call = 0
        
        batch = []
        for row in csv_reader:
            if not row or len(row) <= column_index:
                continue
                
            batch.append(row)
            total_records += 1
            
            if len(batch) >= batch_size:
                # Process batch
                batch_content = '\n'.join([','.join(row) for row in batch])
                batch_result = await process_csv_chunk(batch_content, column_index, db)
                
                all_results.extend(batch_result["data"])
                dnc_matches += batch_result["dnc_matches"]
                safe_to_call += batch_result["safe_to_call"]
                
                batch = []
        
        # Process remaining records
        if batch:
            batch_content = '\n'.join([','.join(row) for row in batch])
            batch_result = await process_csv_chunk(batch_content, column_index, db)
            
            all_results.extend(batch_result["data"])
            dnc_matches += batch_result["dnc_matches"]
            safe_to_call += batch_result["safe_to_call"]
        
        result = {
            "success": True,
            "total_records": total_records,
            "dnc_matches": dnc_matches,
            "safe_to_call": safe_to_call,
            "data": all_results,
            "processed_at": datetime.utcnow().isoformat(),
            "filename": file.filename,
            "batch_size_used": batch_size
        }
        
        logger.info(f"Successfully processed CSV file {file.filename} in batches: {total_records} records, {dnc_matches} DNC matches")
        
        return result
        
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File encoding error. Please ensure the file is UTF-8 encoded."
        )
    except Exception as e:
        logger.error(f"Error processing CSV file {file.filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )


@router.get("/stats")
async def get_dnc_processing_stats(db: Session = Depends(get_db)):
    """Get DNC processing statistics"""
    total_phone_numbers = db.query(PhoneNumber).count()
    dnc_numbers = db.query(PhoneNumber).filter(
        PhoneNumber.status.in_(["completed", "processing"])
    ).count()
    safe_numbers = total_phone_numbers - dnc_numbers
    
    return {
        "total_phone_numbers": total_phone_numbers,
        "dnc_numbers": dnc_numbers,
        "safe_numbers": safe_numbers,
        "dnc_percentage": (dnc_numbers / total_phone_numbers * 100) if total_phone_numbers > 0 else 0
    }
