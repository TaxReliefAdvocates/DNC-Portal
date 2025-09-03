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
from do_not_call.config import settings

router = APIRouter()

# Create uploads directory if it doesn't exist
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

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
                
                # Determine DNC status for CSV
                if dnc_status["is_dnc"]:
                    dnc_csv_status = "DNC_MATCH"
                elif dnc_status["status"] == "invalid":
                    dnc_csv_status = "INVALID_FORMAT"
                elif dnc_status["status"] == "error":
                    dnc_csv_status = "CHECK_ERROR"
                else:
                    dnc_csv_status = "SAFE"
                
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
            "file": f"./uploads/{unique_filename}",
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
