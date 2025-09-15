from typing import Dict, Any
from loguru import logger
from .base import BaseCRMClient
import httpx
from ...config import settings
from datetime import datetime


class ConvosoClient(BaseCRMClient):
    """Convoso dialer platform client"""
    
    def __init__(self):
        self.system_name = "convoso"
        self.base_url = "https://api.convoso.com"  # Replace with actual Convoso API URL
        self.api_key = None  # Will be loaded from environment/config
        
    async def remove_phone_number(self, phone_number: str) -> Dict[str, Any]:
        """
        Remove a phone number from Convoso dialer platform
        
        Args:
            phone_number: Phone number to remove
            
        Returns:
            Dict containing the result of the removal operation
        """
        try:
            logger.info(f"Convoso DNC insert for {phone_number}")
            clean_phone = (
                phone_number.replace('+1','').replace('-','').replace('(','').replace(')','').replace(' ','')
            )
            params = {
                'auth_token': settings.CONVOSO_AUTH_TOKEN or '',
                'phone_number': clean_phone,
                'phone_code': '1',
            }
            url = f"{settings.CONVOSO_BASE_URL}/v1/dnc/insert"
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, params=params, headers={'Cookie': settings.CONVOSO_COOKIE})
                ok = resp.status_code == 200
                data = resp.json() if 'application/json' in resp.headers.get('content-type','') else { 'text': resp.text }
                if not ok:
                    raise Exception(f"Convoso insert error {resp.status_code}: {data}")
                return { 'success': True, 'crm_system': 'convoso', 'status': 'inserted', 'response': data }
        except Exception as e:
            logger.error(f"Failed to insert DNC {phone_number} into Convoso: {e}")
            raise Exception(f"Convoso DNC insert failed: {str(e)}")
    
    async def check_status(self, phone_number: str) -> Dict[str, Any]:
        """
        Check the status of a phone number in Convoso
        
        Args:
            phone_number: Phone number to check
            
        Returns:
            Dict containing the current status
        """
        try:
            logger.info(f"Convoso DNC search for {phone_number}")
            clean_phone = (
                phone_number.replace('+1','').replace('-','').replace('(','').replace(')','').replace(' ','')
            )
            params = {
                'auth_token': settings.CONVOSO_AUTH_TOKEN or '',
                'phone_number': clean_phone,
                'phone_code': '1',
                'offset': 0,
                'limit': 1,
            }
            url = f"{settings.CONVOSO_BASE_URL}/v1/dnc/search"
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, params=params, headers={'Cookie': settings.CONVOSO_COOKIE})
                if resp.status_code != 200:
                    raise Exception(f"Convoso search error {resp.status_code}: {resp.text}")
                data = resp.json() if 'application/json' in resp.headers.get('content-type','') else { 'text': resp.text }
                total = int(data.get('data',{}).get('total',0)) if isinstance(data, dict) else 0
                found = total > 0
                return { 'phone_number': phone_number, 'crm_system': 'convoso', 'status': 'listed' if found else 'not_listed', 'raw': data }
        except Exception as e:
            logger.error(f"Failed Convoso DNC search: {e}")
            raise Exception(f"Convoso DNC search failed: {str(e)}")
    
    async def get_removal_history(self, phone_number: str) -> Dict[str, Any]:
        """
        Get removal history for a phone number in Convoso
        
        Args:
            phone_number: Phone number to get history for
            
        Returns:
            Dict containing removal history
        """
        try:
            # Convoso APIs shown do not provide explicit history; return last search result as placeholder
            return await self.check_status(phone_number)
        except Exception as e:
            logger.error(f"Failed Convoso history: {e}")
            raise

    async def delete_phone_number(self, phone_number: str) -> Dict[str, Any]:
        """Two-step delete from DNC: search to get campaign_id, then delete."""
        try:
            clean_phone = (
                phone_number.replace('+1','').replace('-','').replace('(','').replace(')','').replace(' ','')
            )
            # Step 1: search
            search = await self.check_status(clean_phone)
            raw = search.get('raw') or {}
            try:
                entries = (raw.get('data') or {}).get('entries') or []
            except Exception:
                entries = []
            if not entries:
                return { 'success': False, 'message': 'Phone number not found on DNC list' }
            campaign_id = entries[0].get('campaign_id') or '0'
            url = f"{settings.CONVOSO_BASE_URL}/v1/dnc/delete"
            params = {
                'auth_token': settings.CONVOSO_AUTH_TOKEN or '',
                'phone_number': clean_phone,
                'phone_code': '1',
                'campaign_id': campaign_id,
            }
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.delete(url, params=params, headers={'Cookie': settings.CONVOSO_COOKIE})
                data = resp.json() if 'application/json' in resp.headers.get('content-type','') else { 'text': resp.text }
                if resp.status_code != 200:
                    raise Exception(f"Convoso delete error {resp.status_code}: {data}")
                return { 'success': True, 'crm_system': 'convoso', 'status': 'deleted', 'response': data }
        except Exception as e:
            logger.error(f"Convoso delete failed: {e}")
            raise
