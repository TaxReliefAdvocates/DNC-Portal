from typing import Dict, Any
from loguru import logger

from .base import BaseCRMClient
from ...config import settings


class TrackDriveClient(BaseCRMClient):
    """TrackDrive CRM system integration"""
    
    def __init__(self):
        super().__init__()
        self.base_url = settings.TRACKDRIVE_BASE_URL
        self.api_key = settings.TRACKDRIVE_API_KEY
        
        if not self.api_key:
            logger.warning("TrackDrive API key not configured")
    
    async def remove_phone_number(self, phone_number: str) -> Dict[str, Any]:
        """
        Remove a phone number from TrackDrive's Do Not Call list
        
        Args:
            phone_number: Phone number to remove (formatted as (XXX) XXX-XXXX)
            
        Returns:
            Dict containing the response from TrackDrive
            
        Raises:
            Exception: If the removal fails
        """
        if not self._validate_phone_number(phone_number):
            raise Exception(f"Invalid phone number format: {phone_number}")
        
        formatted_phone = self._format_phone_number(phone_number)
        
        # TrackDrive API endpoint for removing phone numbers
        endpoint = "/api/v1/dnc/remove"
        
        data = {
            "phone_number": formatted_phone,
            "reason": "customer_request",
            "source": "do_not_call_manager"
        }
        
        try:
            response = await self._make_request("POST", endpoint, data=data)
            
            logger.info(f"Successfully removed {phone_number} from TrackDrive")
            
            return {
                "success": True,
                "trackdrive_id": response.get("id"),
                "status": response.get("status", "removed"),
                "message": response.get("message", "Phone number removed successfully"),
                "response": response
            }
            
        except Exception as e:
            logger.error(f"Failed to remove {phone_number} from TrackDrive: {e}")
            raise Exception(f"TrackDrive removal failed: {e}")
    
    async def check_phone_number_status(self, phone_number: str) -> Dict[str, Any]:
        """
        Check the status of a phone number in TrackDrive
        
        Args:
            phone_number: Phone number to check
            
        Returns:
            Dict containing the status information
        """
        if not self._validate_phone_number(phone_number):
            raise Exception(f"Invalid phone number format: {phone_number}")
        
        formatted_phone = self._format_phone_number(phone_number)
        
        # TrackDrive API endpoint for checking phone number status
        endpoint = f"/api/v1/dnc/status/{formatted_phone}"
        
        try:
            response = await self._make_request("GET", endpoint)
            
            return {
                "phone_number": phone_number,
                "is_on_dnc_list": response.get("is_on_dnc_list", False),
                "status": response.get("status"),
                "added_date": response.get("added_date"),
                "last_updated": response.get("last_updated"),
                "response": response
            }
            
        except Exception as e:
            logger.error(f"Failed to check status for {phone_number} in TrackDrive: {e}")
            return {
                "phone_number": phone_number,
                "error": str(e),
                "is_on_dnc_list": None,
                "status": "error"
            }
    
    async def bulk_remove_phone_numbers(self, phone_numbers: list[str]) -> Dict[str, Any]:
        """
        Remove multiple phone numbers from TrackDrive's Do Not Call list
        
        Args:
            phone_numbers: List of phone numbers to remove
            
        Returns:
            Dict containing the bulk removal results
        """
        if not phone_numbers:
            return {"success": True, "removed": [], "failed": []}
        
        # Validate all phone numbers
        valid_numbers = []
        invalid_numbers = []
        
        for phone in phone_numbers:
            if self._validate_phone_number(phone):
                valid_numbers.append(self._format_phone_number(phone))
            else:
                invalid_numbers.append(phone)
        
        if not valid_numbers:
            return {
                "success": False,
                "removed": [],
                "failed": invalid_numbers,
                "error": "No valid phone numbers provided"
            }
        
        # TrackDrive bulk removal endpoint
        endpoint = "/api/v1/dnc/bulk-remove"
        
        data = {
            "phone_numbers": valid_numbers,
            "reason": "customer_request",
            "source": "do_not_call_manager"
        }
        
        try:
            response = await self._make_request("POST", endpoint, data=data)
            
            # Process results
            removed = response.get("removed", [])
            failed = response.get("failed", [])
            
            # Add invalid numbers to failed list
            failed.extend(invalid_numbers)
            
            logger.info(f"Bulk removal completed: {len(removed)} removed, {len(failed)} failed")
            
            return {
                "success": True,
                "removed": removed,
                "failed": failed,
                "total_processed": len(phone_numbers),
                "response": response
            }
            
        except Exception as e:
            logger.error(f"Bulk removal failed: {e}")
            return {
                "success": False,
                "removed": [],
                "failed": phone_numbers,
                "error": str(e)
            }
    
    async def get_dnc_list_stats(self) -> Dict[str, Any]:
        """
        Get statistics about TrackDrive's Do Not Call list
        
        Returns:
            Dict containing DNC list statistics
        """
        endpoint = "/api/v1/dnc/stats"
        
        try:
            response = await self._make_request("GET", endpoint)
            
            return {
                "total_numbers": response.get("total_numbers", 0),
                "recent_additions": response.get("recent_additions", 0),
                "last_updated": response.get("last_updated"),
                "response": response
            }
            
        except Exception as e:
            logger.error(f"Failed to get TrackDrive DNC stats: {e}")
            return {
                "error": str(e),
                "total_numbers": 0,
                "recent_additions": 0
            }



