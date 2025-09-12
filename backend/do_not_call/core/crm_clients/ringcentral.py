from typing import Dict, Any, Optional
from loguru import logger
from .base import BaseCRMClient
import httpx
from ...config import settings
from datetime import datetime, timedelta
import base64
from ...core.utils import normalize_phone_to_e164_digits


class RingCentralClient(BaseCRMClient):
    """Ring Central communication platform client"""
    
    def __init__(self):
        self.system_name = "ringcentral"
        self.base_url = settings.RINGCENTRAL_BASE_URL.rstrip("/")
        self._access_token: Optional[str] = settings.RINGCENTRAL_ACCESS_TOKEN
        self._token_expiry: Optional[datetime] = None
        self._account_id: Optional[str] = None
        self._extension_id: Optional[str] = None

    async def _ensure_token(self) -> None:
        if self._access_token and self._token_expiry and datetime.utcnow() < self._token_expiry:
            return
        auth = base64.b64encode(f"{settings.RINGCENTRAL_CLIENT_ID}:{settings.RINGCENTRAL_CLIENT_SECRET}".encode()).decode()
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": settings.RINGCENTRAL_JWT_TOKEN or "",
        }
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{self.base_url}/restapi/oauth/token", data=data, headers=headers)
            if resp.status_code != 200:
                raise Exception(f"RingCentral auth failed {resp.status_code}: {resp.text}")
            payload = resp.json()
            self._access_token = payload.get("access_token")
            expires_in = int(payload.get("expires_in", 3600))
            self._token_expiry = datetime.utcnow() + timedelta(seconds=max(60, expires_in - 60))

    async def _ensure_account_and_extension(self) -> None:
        await self._ensure_token()
        headers = {"Authorization": f"Bearer {self._access_token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=30) as client:
            # Account discovery
            if not self._account_id or self._account_id == "~":
                r1 = await client.get(f"{self.base_url}/restapi/v1.0/account/~", headers=headers)
                if r1.status_code != 200:
                    raise Exception(f"Account discovery failed: {r1.text}")
                self._account_id = (r1.json() or {}).get("id") or "~"
            # Extension discovery
            if not self._extension_id or self._extension_id == "~":
                r2 = await client.get(f"{self.base_url}/restapi/v1.0/account/~/extension/~", headers=headers)
                if r2.status_code != 200:
                    raise Exception(f"Extension discovery failed: {r2.text}")
                self._extension_id = (r2.json() or {}).get("id") or "~"

    async def auth_status(self) -> Dict[str, Any]:
        try:
            await self._ensure_account_and_extension()
            return {
                "authenticated": True,
                "account_id": self._account_id,
                "extension_id": self._extension_id,
                "token_expires_at": self._token_expiry.isoformat() if self._token_expiry else None,
            }
        except Exception as e:
            return {"authenticated": False, "error": str(e)}
        
    async def remove_phone_number(self, phone_number: str) -> Dict[str, Any]:
        """
        Remove a phone number from Ring Central platform
        
        Args:
            phone_number: Phone number to remove
            
        Returns:
            Dict containing the result of the removal operation
        """
        try:
            # Validate and format number
            digits = normalize_phone_to_e164_digits(phone_number)
            if not digits:
                raise Exception("Invalid phone number format")
            await self._ensure_account_and_extension()
            logger.info(f"Adding phone number +1{digits} to RingCentral blocked list")
            url = f"{self.base_url}/restapi/v1.0/account/{self._account_id}/extension/{self._extension_id}/caller-blocking/phone-numbers"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            payload = { "phoneNumber": f"+1{digits}", "status": "Blocked" }
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, headers=headers, json=payload)
                ok = resp.status_code in (200, 201)
                data = resp.json() if resp.headers.get('content-type','').startswith('application/json') else {"text": resp.text}
                if not ok:
                    raise Exception(f"RingCentral error {resp.status_code}: {data}")
                return {
                    "success": True,
                    "phone_number": f"+1{digits}",
                    "crm_system": "ringcentral",
                    "status": "blocked",
                    "response": data,
                    "timestamp": datetime.now().isoformat(),
                }
        except Exception as e:
            logger.error(f"Failed to block {phone_number} on RingCentral: {e}")
            raise Exception(f"RingCentral block failed: {str(e)}")
    
    async def check_status(self, phone_number: str) -> Dict[str, Any]:
        """
        Check the status of a phone number in Ring Central
        
        Args:
            phone_number: Phone number to check
            
        Returns:
            Dict containing the current status
        """
        try:
            digits = normalize_phone_to_e164_digits(phone_number)
            if not digits:
                raise Exception("Invalid phone number format")
            await self._ensure_account_and_extension()
            logger.info(f"Listing blocked numbers to check status for +1{digits}")
            url = f"{self.base_url}/restapi/v1.0/account/{self._account_id}/extension/{self._extension_id}/caller-blocking/phone-numbers"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Accept": "application/json",
            }
            params = { "page": 1, "perPage": 100, "status": "Blocked", "phoneNumber": f"+1{digits}" }
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code != 200:
                    raise Exception(f"RingCentral list error {resp.status_code}: {resp.text}")
                data = resp.json()
                items = data.get('records') or data.get('phoneNumbers') or []
                blocked = any((item.get('phoneNumber') or item.get('blockedNumber')) == f"+1{digits}" for item in items)
                return {
                    "phone_number": f"+1{digits}",
                    "crm_system": "ringcentral",
                    "status": "blocked" if blocked else "not_blocked",
                    "last_updated": datetime.now().isoformat(),
                    "raw": data,
                }
        except Exception as e:
            logger.error(f"Failed to check status of {phone_number} in RingCentral: {e}")
            raise Exception(f"RingCentral status check failed: {str(e)}")
    
    async def get_removal_history(self, phone_number: str) -> Dict[str, Any]:
        """
        Get removal history for a phone number in Ring Central
        
        Args:
            phone_number: Phone number to get history for
            
        Returns:
            Dict containing removal history
        """
        try:
            logger.info(f"Getting removal history for {phone_number} in Ring Central")
            
            # TODO: Implement actual Ring Central API call here
            # This is a placeholder implementation
            
            result = {
                "phone_number": phone_number,
                "crm_system": "ringcentral",
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
            logger.error(f"Failed to get removal history for {phone_number} in Ring Central: {e}")
            raise Exception(f"Ring Central history retrieval failed: {str(e)}")
