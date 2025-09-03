"""
DNC Service for checking phone numbers against federal Do Not Call lists
"""
import asyncio
import aiohttp
import re
from typing import Dict, Any, Optional
from loguru import logger
from do_not_call.config import settings


class DNCService:
    """Service for checking phone numbers against DNC lists"""
    
    def __init__(self):
        self.fcc_api_url = "https://www.donotcall.gov/api/check"
        self.fcc_api_key = getattr(settings, 'FCC_API_KEY', None)
        self.timeout = 30  # seconds
        
        # Sample DNC patterns for demonstration
        # In production, replace this with actual DNC API calls
        self.dnc_patterns = [
            # Common DNC patterns (these are examples - replace with real logic)
            r'555-000-\d{4}',  # Example: 555-000-XXXX numbers
            r'555-999-\d{4}',  # Example: 555-999-XXXX numbers
        ]
        
    async def check_federal_dnc(self, phone_number: str) -> Dict[str, Any]:
        """
        Check if a phone number is on the federal DNC list
        
        Args:
            phone_number: Phone number to check (should be normalized)
            
        Returns:
            Dict containing DNC status information
        """
        try:
            # Remove any non-digit characters for API call
            clean_number = ''.join(filter(str.isdigit, phone_number))
            
            if not clean_number or len(clean_number) < 10:
                return {
                    "is_dnc": False,
                    "dnc_source": "invalid_format",
                    "status": "invalid",
                    "notes": "Phone number format is invalid"
                }
            
            # Use FCC DNC API if available
            if self.fcc_api_key:
                return await self._check_fcc_dnc(clean_number)
            
            # Fallback to pattern-based check (replace with real DNC service)
            return await self._check_pattern_dnc(phone_number)
            
        except Exception as e:
            logger.error(f"Error checking federal DNC for {phone_number}: {e}")
            return {
                "is_dnc": False,
                "dnc_source": "error",
                "status": "error",
                "notes": f"Error checking DNC: {str(e)}"
            }
    
    async def _check_fcc_dnc(self, phone_number: str) -> Dict[str, Any]:
        """Check DNC status using FCC API"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                params = {
                    'phone': phone_number,
                    'api_key': self.fcc_api_key
                }
                
                async with session.get(self.fcc_api_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Parse FCC API response (adjust based on actual API response format)
                        is_dnc = data.get('is_dnc', False)
                        dnc_source = data.get('source', 'federal_dnc')
                        
                        return {
                            "is_dnc": is_dnc,
                            "dnc_source": dnc_source,
                            "status": "dnc_listed" if is_dnc else "safe_to_call",
                            "notes": f"Checked against FCC DNC list - {'Listed' if is_dnc else 'Not listed'}"
                        }
                    else:
                        logger.warning(f"FCC API returned status {response.status}")
                        return await self._check_pattern_dnc(phone_number)
                        
        except asyncio.TimeoutError:
            logger.warning(f"FCC API timeout for {phone_number}")
            return await self._check_pattern_dnc(phone_number)
        except Exception as e:
            logger.error(f"FCC API error for {phone_number}: {e}")
            return await self._check_pattern_dnc(phone_number)
    
    async def _check_pattern_dnc(self, phone_number: str) -> Dict[str, Any]:
        """
        Pattern-based DNC check - replace this with actual DNC service integration
        
        This is a demonstration implementation. In production, you would:
        1. Call a real DNC API service
        2. Check against your own DNC database
        3. Integrate with services like Twilio, CallFire, etc.
        """
        try:
            # Normalize phone number for pattern matching
            normalized = re.sub(r'[^\d]', '', phone_number)
            
            # Check against DNC patterns (replace with real DNC logic)
            for pattern in self.dnc_patterns:
                if re.match(pattern, phone_number):
                    return {
                        "is_dnc": True,
                        "dnc_source": "pattern_match",
                        "status": "dnc_listed",
                        "notes": f"Phone number matches DNC pattern: {pattern}"
                    }
            
            # For demonstration, let's mark some numbers as DNC based on simple rules
            # Replace this with actual DNC checking logic
            
            # Example: Check if number ends with certain digits (this is just for demo)
            if normalized.endswith('0000') or normalized.endswith('9999'):
                return {
                    "is_dnc": True,
                    "dnc_source": "demo_pattern",
                    "status": "dnc_listed",
                    "notes": "Phone number matches demo DNC pattern (ends with 0000 or 9999)"
                }
            
            # Example: Check if number is in a specific range (demo only)
            if normalized.startswith('555') and int(normalized[3:6]) in [111, 222, 333]:
                return {
                    "is_dnc": True,
                    "dnc_source": "demo_range",
                    "status": "dnc_listed",
                    "notes": "Phone number in demo DNC range (555-111, 555-222, 555-333)"
                }
            
            # If no DNC patterns match, return safe to call
            return {
                "is_dnc": False,
                "dnc_source": "demo_check",
                "status": "safe_to_call",
                "notes": "Phone number passed demo DNC check - replace with real DNC service"
            }
            
        except Exception as e:
            logger.error(f"Error in pattern DNC check for {phone_number}: {e}")
            return {
                "is_dnc": False,
                "dnc_source": "error",
                "status": "error",
                "notes": f"Pattern DNC check error: {str(e)}"
            }
    
    async def _check_manual_dnc(self, phone_number: str) -> Dict[str, Any]:
        """
        Manual DNC check - implement your own DNC checking logic here
        This could include:
        - Checking against a local DNC database
        - Calling other DNC services
        - Implementing business logic for DNC compliance
        """
        try:
            # For demonstration, let's implement a simple check
            # In production, you would integrate with actual DNC services
            
            # Example: Check if number ends with certain patterns that might indicate DNC
            # This is just a placeholder - replace with real DNC checking logic
            
            # You could also check against a local database of known DNC numbers
            # or integrate with services like:
            # - Twilio's DNC API
            # - CallFire's DNC API
            # - Your own DNC database
            
            # For now, return a placeholder that indicates manual checking is needed
            return {
                "is_dnc": False,
                "dnc_source": "manual_check_required",
                "status": "manual_check_required",
                "notes": "Manual DNC verification required - integrate with DNC service"
            }
            
        except Exception as e:
            logger.error(f"Error in manual DNC check for {phone_number}: {e}")
            return {
                "is_dnc": False,
                "dnc_source": "error",
                "status": "error",
                "notes": f"Manual DNC check error: {str(e)}"
            }
    
    async def batch_check_dnc(self, phone_numbers: list) -> Dict[str, list]:
        """
        Check multiple phone numbers against DNC lists
        
        Args:
            phone_numbers: List of phone numbers to check
            
        Returns:
            Dict containing results for each phone number
        """
        results = []
        
        # Process in smaller batches to avoid overwhelming APIs
        batch_size = 50
        for i in range(0, len(phone_numbers), batch_size):
            batch = phone_numbers[i:i + batch_size]
            
            # Create tasks for concurrent processing
            tasks = [self.check_federal_dnc(phone) for phone in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    results.append({
                        "phone_number": batch[j],
                        "is_dnc": False,
                        "dnc_source": "error",
                        "status": "error",
                        "notes": f"Exception: {str(result)}"
                    })
                else:
                    results.append({
                        "phone_number": batch[j],
                        **result
                    })
            
            # Add small delay between batches to be respectful to APIs
            if i + batch_size < len(phone_numbers):
                await asyncio.sleep(0.1)
        
        return {"results": results}


# Global instance
dnc_service = DNCService()
