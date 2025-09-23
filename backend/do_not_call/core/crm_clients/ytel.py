from typing import Dict, Any
from loguru import logger
from .base import BaseCRMClient
import httpx
from ...config import settings
from datetime import datetime


class YtelClient(BaseCRMClient):
    """Ytel communication platform client"""
    
    def __init__(self):
        self.system_name = "ytel"
        self.base_url = "https://api.ytel.com"  # Replace with actual Ytel API URL
        self.api_key = None  # Will be loaded from environment/config
        
    async def remove_phone_number(self, phone_number: str) -> Dict[str, Any]:
        """
        Remove a phone number from Ytel communication platform
        
        Args:
            phone_number: Phone number to remove
            
        Returns:
            Dict containing the result of the removal operation
        """
        try:
            logger.info(f"Removing phone number {phone_number} from Ytel")
            # Prefer v4 API if bearer token present; else fallback to legacy non_agent
            if settings.YTEL_BEARER_TOKEN:
                url = f"{settings.YTEL_V4_BASE_URL}/dnc"
                headers = {"Authorization": f"Bearer {settings.YTEL_BEARER_TOKEN}", "Content-Type": "application/json"}
                payload = {
                    "endpoint": phone_number,
                    "selector": settings.YTEL_SELECTOR_DEFAULT,
                    "subtype": "call",
                }
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    ok = resp.status_code in (200, 201)
                    data = resp.json() if 'application/json' in resp.headers.get('content-type','') else { 'text': resp.text }
                    if not ok:
                        raise Exception(f"Ytel v4 error {resp.status_code}: {data}")
                    return { "success": True, "phone_number": phone_number, "crm_system": "ytel", "status": "removed", "response": data }
            else:
                params = {
                    "function": "update_lead",
                    "user": settings.YTEL_USER or "",
                    "pass": settings.YTEL_PASS or "",
                    "source": "dncfilter",
                    "status": "DNC",
                    "phone_number": phone_number,
                    "ADDTODNC": settings.YTEL_ADD_TO_DNC,
                    "CAMPAIGN": settings.YTEL_CAMPAIGN,
                }
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(settings.YTEL_NON_AGENT_URL, params=params)
                    body = resp.text.strip()
                    ok = resp.status_code == 200 and ("ALREADY" in body.upper() or "DNC" in body.upper() or "SUCCESS" in body.upper())
                    result = {
                        "success": ok,
                        "phone_number": phone_number,
                        "crm_system": "ytel",
                        "status": "removed" if ok else "failed",
                        "message": body,
                        "http_status": resp.status_code,
                        "timestamp": datetime.now().isoformat(),
                    }
                    if not ok:
                        raise Exception(f"Ytel responded with {resp.status_code}: {body}")
                    logger.info(f"Ytel DNC add response for {phone_number}: {body}")
                    return result
        except Exception as e:
            logger.error(f"Failed to remove {phone_number} from Ytel: {e}")
            raise Exception(f"Ytel removal failed: {str(e)}")
    
    async def check_status(self, phone_number: str) -> Dict[str, Any]:
        """Mimic Ytel non_agent check using add_lead with DNC checks enabled.

        Example (provided):
        https://tra.ytel.com/x5/api/non_agent.php?function=add_lead&user=103&pass=bHSQPgE7J6nLzX&source=dncfilter&phone_number=5618189087&dnc_check=Y&campaign_dnc_check=Y&duplicate_check=Y
        """
        try:
            logger.info(f"Ytel DNC search for {phone_number}")
            clean_phone = (
                phone_number.replace('+1','').replace('-','').replace('(','').replace(')','').replace(' ','')
            )
            params = {
                "function": "add_lead",
                "user": settings.YTEL_USER or "",
                "pass": settings.YTEL_PASS or "",
                "source": settings.YTEL_ADD_TO_DNC.lower() if settings.YTEL_ADD_TO_DNC else "dncfilter",
                "phone_number": clean_phone,
                "dnc_check": "Y",
                "campaign_dnc_check": "Y",
                "duplicate_check": "Y",
            }
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(settings.YTEL_NON_AGENT_URL, params=params)
                body = (resp.text or "").strip()
                ok = resp.status_code == 200
                # Ytel returns ERROR lines for DNC present; treat that as listed
                listed = ("PHONE NUMBER IN DNC" in body.upper()) or ("DNC" in body.upper() and "PHONE" in body.upper())
                return {
                    "success": ok,
                    "phone_number": clean_phone,
                    "crm_system": "ytel",
                    "listed": listed,
                    "message": body,
                    "http_status": resp.status_code,
                    "checked_at": datetime.now().isoformat(),
                }
        except Exception as e:
            logger.error(f"Ytel search failed for {phone_number}: {e}")
            raise Exception(f"Ytel search failed: {str(e)}")
    
    async def get_removal_history(self, phone_number: str) -> Dict[str, Any]:
        """
        Get removal history for a phone number in Ytel
        
        Args:
            phone_number: Phone number to get history for
            
        Returns:
            Dict containing removal history
        """
        try:
            logger.info(f"Getting removal history for {phone_number} in Ytel")
            
            # TODO: Implement actual Ytel API call here
            # This is a placeholder implementation
            
            result = {
                "phone_number": phone_number,
                "crm_system": "ytel",
                "history": [
                    {
                        "action": "removal_requested",
                        "timestamp": datetime.now().isoformat(),
                        "status": "completed",
                        "user": "system"
                    }
                ],
                "total_actions": 1
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get removal history for {phone_number} in Ytel: {e}")
            raise Exception(f"Ytel history retrieval failed: {str(e)}")
