from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import httpx
from loguru import logger


class BaseCRMClient(ABC):
    """Base class for CRM system integrations"""
    
    def __init__(self):
        self.base_url: str = ""
        self.api_key: Optional[str] = None
        self.timeout: int = 30
        self.max_retries: int = 3
    
    @abstractmethod
    async def remove_phone_number(self, phone_number: str) -> Dict[str, Any]:
        """
        Remove a phone number from the CRM system's Do Not Call list
        
        Args:
            phone_number: Phone number to remove (formatted as (XXX) XXX-XXXX)
            
        Returns:
            Dict containing the response from the CRM system
            
        Raises:
            Exception: If the removal fails
        """
        pass
    
    @abstractmethod
    async def check_phone_number_status(self, phone_number: str) -> Dict[str, Any]:
        """
        Check the status of a phone number in the CRM system
        
        Args:
            phone_number: Phone number to check
            
        Returns:
            Dict containing the status information
        """
        pass
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to CRM API
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            data: Request data
            headers: Request headers
            
        Returns:
            Response data as dictionary
            
        Raises:
            Exception: If the request fails
        """
        if headers is None:
            headers = {}
        
        # Add default headers
        headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Do-Not-Call-Manager/1.0.0"
        })
        
        # Add API key if available
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    logger.debug(f"Making {method} request to {url} (attempt {attempt + 1})")
                    
                    response = await client.request(
                        method=method,
                        url=url,
                        json=data,
                        headers=headers
                    )
                    
                    response.raise_for_status()
                    
                    # Try to parse JSON response
                    try:
                        return response.json()
                    except ValueError:
                        # Return text response if not JSON
                        return {"text": response.text}
                        
                except httpx.HTTPStatusError as e:
                    logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
                    if attempt == self.max_retries - 1:
                        raise Exception(f"HTTP {e.response.status_code}: {e.response.text}")
                    
                except httpx.RequestError as e:
                    logger.error(f"Request error: {e}")
                    if attempt == self.max_retries - 1:
                        raise Exception(f"Request failed: {e}")
                    
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    if attempt == self.max_retries - 1:
                        raise
    
    def _format_phone_number(self, phone_number: str) -> str:
        """
        Format phone number for CRM system
        
        Args:
            phone_number: Phone number in (XXX) XXX-XXXX format
            
        Returns:
            Formatted phone number
        """
        # Remove formatting and return just digits
        return ''.join(filter(str.isdigit, phone_number))
    
    def _validate_phone_number(self, phone_number: str) -> bool:
        """
        Validate phone number format
        
        Args:
            phone_number: Phone number to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Remove all non-digit characters
        digits = ''.join(filter(str.isdigit, phone_number))
        
        # Check if it's a valid US phone number (10 digits)
        return len(digits) == 10
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check if the CRM system is healthy/accessible
        
        Returns:
            Health status information
        """
        try:
            response = await self._make_request("GET", "/health")
            return {
                "status": "healthy",
                "response": response
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }





