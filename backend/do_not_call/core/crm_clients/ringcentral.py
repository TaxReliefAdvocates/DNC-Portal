from typing import Dict, Any, Optional, List
import os
import base64
from datetime import datetime, timedelta
import httpx
from loguru import logger


class RingCentralService:
    """Concrete RingCentral service for auth, discovery, and DNC operations."""

    def __init__(self):
        self.client_id: Optional[str] = os.getenv("RINGCENTRAL_CLIENT_ID")
        self.client_secret: Optional[str] = os.getenv("RINGCENTRAL_CLIENT_SECRET")
        # Allow either RINGCENTRAL_JWT_TOKEN or RINGCENTRAL_JWT
        self.jwt_token: Optional[str] = os.getenv("RINGCENTRAL_JWT_TOKEN") or os.getenv("RINGCENTRAL_JWT")
        self.base_url: str = os.getenv("RINGCENTRAL_BASE_URL", "https://platform.ringcentral.com").rstrip("/")
        self.cookie: Optional[str] = os.getenv("RINGCENTRAL_COOKIE")
        self.access_token: Optional[str] = None
        self.account_id: Optional[str] = None
        self.extension_id: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

    def _format_e164(self, phone_number: str) -> str:
        digits = ''.join(ch for ch in phone_number if ch.isdigit())
        if digits.startswith('1') and len(digits) == 11:
            return f"+{digits}"
        if len(digits) == 10:
            return f"+1{digits}"
        if phone_number.startswith('+'):
            return phone_number
        raise ValueError("Invalid phone number format")

    async def authenticate(self) -> None:
        """Get access token using JWT assertion. Raises on failure with detailed reason."""
        missing = [k for k,v in {
            'RINGCENTRAL_CLIENT_ID': self.client_id,
            'RINGCENTRAL_CLIENT_SECRET': self.client_secret,
            'RINGCENTRAL_JWT_TOKEN/RINGCENTRAL_JWT': self.jwt_token,
        }.items() if not v]
        if missing:
            raise Exception(f"Missing RingCentral env: {', '.join(missing)}")

        auth_b64 = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode("ascii")).decode("ascii")
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {auth_b64}'
        }
        if self.cookie:
            headers['Cookie'] = self.cookie
        data = {
            'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            'assertion': self.jwt_token
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{self.base_url}/restapi/oauth/token", headers=headers, data=data)
            if resp.status_code != 200:
                # Try to include RC error body for debugging
                text = resp.text
                raise Exception(f"RingCentral auth failed {resp.status_code}: {text}")
            token_data = resp.json()
            self.access_token = token_data.get('access_token')
            expires_in = int(token_data.get('expires_in', 3600))
            # refresh 60s early
            self.token_expires_at = datetime.now() + timedelta(seconds=max(60, expires_in - 60))

    async def _ensure_token_valid(self) -> None:
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
            return
        await self.authenticate()

    async def discover_account_info(self) -> tuple[str, str]:
        """Discover account and extension IDs using ~ endpoints."""
        await self._ensure_token_valid()
        headers = {'Authorization': f'Bearer {self.access_token}'}
        async with httpx.AsyncClient(timeout=30) as client:
            a = await client.get(f"{self.base_url}/restapi/v1.0/account/~", headers=headers)
            if a.status_code != 200:
                raise Exception(f"Account discovery failed: {a.text}")
            self.account_id = str((a.json() or {}).get('id'))
            e = await client.get(f"{self.base_url}/restapi/v1.0/account/~/extension/~", headers=headers)
            if e.status_code != 200:
                raise Exception(f"Extension discovery failed: {e.text}")
            self.extension_id = str((e.json() or {}).get('id'))
        return self.account_id, self.extension_id

    async def _ensure_context(self) -> None:
        if not self.access_token or not self.token_expires_at or datetime.now() >= self.token_expires_at:
            await self.authenticate()
        if not self.account_id or not self.extension_id:
            await self.discover_account_info()

    async def add_blocked_number(self, phone_number: str, label: str = "API Block") -> Dict[str, Any]:
        await self._ensure_context()
        formatted_phone = self._format_e164(phone_number)
        headers = {'Authorization': f'Bearer {self.access_token}', 'Content-Type': 'application/json'}
        data = {"phoneNumber": formatted_phone, "label": label, "status": "Blocked"}
        url = f"{self.base_url}/restapi/v1.0/account/{self.account_id}/extension/{self.extension_id}/caller-blocking/phone-numbers"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=data)
            if resp.status_code not in (200, 201):
                raise Exception(f"Add blocked failed {resp.status_code}: {resp.text}")
            return resp.json() if resp.headers.get('content-type','').startswith('application/json') else {"text": resp.text}

    async def list_blocked_numbers(self) -> List[Dict[str, Any]]:
        await self._ensure_context()
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.base_url}/restapi/v1.0/account/{self.account_id}/extension/{self.extension_id}/caller-blocking/phone-numbers"
        params = {"status": "Blocked", "page": 1, "perPage": 100}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                raise Exception(f"List blocked failed {resp.status_code}: {resp.text}")
            data = resp.json()
            return data.get('records', data.get('phoneNumbers', []))

    async def search_blocked_number(self, phone_number: str) -> Dict[str, Any]:
        await self._ensure_context()
        formatted_phone = self._format_e164(phone_number)
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.base_url}/restapi/v1.0/account/{self.account_id}/extension/{self.extension_id}/caller-blocking/phone-numbers"
        params = {"status": "Blocked", "phoneNumber": formatted_phone, "page": 1, "perPage": 100}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                raise Exception(f"Search failed {resp.status_code}: {resp.text}")
            data = resp.json()
            records = data.get('records', data.get('phoneNumbers', []))
            found = next((r for r in records if r.get('phoneNumber') == formatted_phone), None)
            return {"found": bool(found), "record": found, "raw": data}

    async def remove_blocked_number(self, phone_number: str) -> bool:
        await self._ensure_context()
        formatted_phone = self._format_e164(phone_number)
        # find id
        result = await self.search_blocked_number(formatted_phone)
        record = result.get('record')
        if not record:
            return False
        blocked_id = record.get('id')
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.base_url}/restapi/v1.0/account/{self.account_id}/extension/{self.extension_id}/caller-blocking/phone-numbers/{blocked_id}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(url, headers=headers)
            return resp.status_code in (200, 204)

    # Compatibility methods used elsewhere in the app
    async def remove_phone_number(self, phone_number: str) -> Dict[str, Any]:
        """For consistency with other clients: add to RingCentral blocked list."""
        payload = await self.add_blocked_number(phone_number, label="API Block")
        formatted = self._format_e164(phone_number)
        return {
            "success": True,
            "phone_number": formatted,
            "crm_system": "ringcentral",
            "status": "blocked",
            "response": payload,
            "timestamp": datetime.now().isoformat(),
        }

    async def check_status(self, phone_number: str) -> Dict[str, Any]:
        res = await self.search_blocked_number(phone_number)
        formatted = self._format_e164(phone_number)
        return {
            "phone_number": formatted,
            "crm_system": "ringcentral",
            "status": "blocked" if res.get("found") else "not_blocked",
            "last_updated": datetime.now().isoformat(),
            "raw": res.get("raw"),
        }

    async def auth_status(self) -> Dict[str, Any]:
        try:
            await self._ensure_context()
            return {
                "authenticated": True,
                "account_id": self.account_id,
                "extension_id": self.extension_id,
                "token_expires_at": self.token_expires_at.isoformat() if self.token_expires_at else None,
            }
        except Exception as e:
            return {"authenticated": False, "error": str(e)}
