"""
DNC Service for checking phone numbers against federal Do Not Call lists
"""
import asyncio
import aiohttp
import ssl
import re
from typing import Dict, Any, Optional, List
from loguru import logger
from do_not_call.config import settings
from do_not_call.core.cookie_fetcher import fetch_freednclist_phpsessid


class DNCService:
    """Service for checking phone numbers against DNC lists"""
    
    def __init__(self):
        self.fcc_api_url = "https://www.donotcall.gov/api/check"
        self.fcc_api_key = getattr(settings, 'FCC_API_KEY', None)
        self.freednclist_url = "https://freednclist.com/check_number.php"
        self.timeout = 30  # seconds
        
        # Create SSL context that skips certificate verification for FreeDNCList
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
        # FreeDNCList.com session cookie; fetched dynamically when needed
        self.freednclist_session: Optional[str] = None
        self._session_fetch_attempted: bool = False

    async def _ensure_freednclist_session(self) -> None:
        """Ensure we have a current PHPSESSID from freednclist.com."""
        if self.freednclist_session or self._session_fetch_attempted:
            return
        self._session_fetch_attempted = True
        if not self.freednclist_session:
            try:
                session_id = await fetch_freednclist_phpsessid()
                if session_id:
                    self.freednclist_session = session_id
                    logger.info("Obtained new FreeDNCList PHPSESSID")
                else:
                    logger.warning("Could not obtain PHPSESSID from FreeDNCList; proceeding without cookie")
            except Exception as e:
                logger.error(f"Error fetching FreeDNCList PHPSESSID: {e}")
        
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
            
            # Use FreeDNCList.com API as primary DNC checking service
            return await self._check_freednclist_api(clean_number)
            
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
                        return await self._check_freednclist_api(phone_number)
                        
        except asyncio.TimeoutError:
            logger.warning(f"FCC API timeout for {phone_number}")
            return await self._check_freednclist_api(phone_number)
        except Exception as e:
            logger.error(f"FCC API error for {phone_number}: {e}")
            return await self._check_freednclist_api(phone_number)
    
    async def _check_freednclist_api(self, phone_number: str) -> Dict[str, Any]:
        """
        Check DNC status using FreeDNCList.com API
        
        This replicates the exact curl command you provided
        """
        try:
            headers = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/json',
                'origin': 'https://freednclist.com',
                'priority': 'u=1, i',
                'referer': 'https://freednclist.com/',
                'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36'
            }
            
            # Ensure we have a cookie; FreeDNCList often requires a session
            await self._ensure_freednclist_session()
            cookies = {'PHPSESSID': self.freednclist_session} if self.freednclist_session else None
            
            payload = {
                "phone_number": phone_number
            }
            
            # Create connector with SSL context that skips certificate verification
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                connector=connector,
                cookies=cookies
            ) as session:
                async with session.post(
                    self.freednclist_url,
                    json=payload,
                    headers=headers
                ) as response:
                    
                    if response.status == 200:
                        # Try to parse JSON regardless of content-type (site may return JSON with text/html)
                        content_type = response.headers.get('content-type', '')
                        try:
                            data = await response.json(content_type=None)
                        except Exception:
                            # Fallback: read text and try manual JSON parse if it looks like JSON
                            text_body = await response.text()
                            logger.warning(f"FreeDNCList non-JSON content-type {content_type}; body preview: {text_body[:120]}...")
                            try:
                                import json as _json
                                data = _json.loads(text_body)
                            except Exception:
                                # Try alternative approach - maybe they expect form data instead of JSON
                                return await self._check_freednclist_form_data(phone_number)

                        logger.info(f"FreeDNCList API response for {phone_number}: {data}")
                        # Parse FreeDNCList API response. Accept alternate keys commonly seen.
                        is_dnc = bool(
                            data.get('is_dnc')
                            or data.get('dnc_status')
                            or data.get('exists')
                        )
                        dnc_source = data.get('source', 'freednclist')
                        notes = data.get('message') or data.get('error') or (
                            "Checked against FreeDNCList.com - " + ("Listed" if is_dnc else "Not listed")
                        )
                        return {
                            "is_dnc": is_dnc,
                            "dnc_source": dnc_source,
                            "status": "dnc_listed" if is_dnc else "safe_to_call",
                            "notes": notes,
                        }
                    else:
                        logger.warning(f"FreeDNCList API returned status {response.status}")
                        # Try one-time refresh of cookie and retry once
                        if response.status in (401, 403):
                            logger.info("Refreshing FreeDNCList cookie and retrying once...")
                            # Force refresh
                            self.freednclist_session = None
                            self._session_fetch_attempted = False
                            await self._ensure_freednclist_session()
                            retry_cookies = {'PHPSESSID': self.freednclist_session} if self.freednclist_session else None
                            async with aiohttp.ClientSession(
                                timeout=aiohttp.ClientTimeout(total=self.timeout),
                                connector=connector,
                                cookies=retry_cookies
                            ) as retry_session:
                                async with retry_session.post(
                                    self.freednclist_url,
                                    json=payload,
                                    headers=headers
                                ) as retry_response:
                                    if retry_response.status == 200:
                                        content_type = retry_response.headers.get('content-type', '')
                                        if 'application/json' in content_type:
                                            data = await retry_response.json()
                                            is_dnc = data.get('is_dnc', False) or data.get('dnc_status', False)
                                            dnc_source = data.get('source', 'freednclist')
                                            return {
                                                "is_dnc": is_dnc,
                                                "dnc_source": dnc_source,
                                                "status": "dnc_listed" if is_dnc else "safe_to_call",
                                                "notes": "Checked against FreeDNCList.com - retry success"
                                            }
                                    # fallthrough to error below if retry not successful
                        return {
                            "is_dnc": False,
                            "dnc_source": "freednclist_error",
                            "status": "api_error",
                            "notes": f"FreeDNCList API error: HTTP {response.status}"
                        }
                        
        except asyncio.TimeoutError:
            logger.warning(f"FreeDNCList API timeout for {phone_number}")
            return {
                "is_dnc": False,
                "dnc_source": "freednclist_timeout",
                "status": "timeout",
                "notes": "FreeDNCList API timeout"
            }
        except Exception as e:
            logger.error(f"FreeDNCList API error for {phone_number}: {e}")
            return {
                "is_dnc": False,
                "dnc_source": "freednclist_error",
                "status": "error",
                "notes": f"FreeDNCList API error: {str(e)}"
            }
    
    async def _check_freednclist_form_data(self, phone_number: str) -> Dict[str, Any]:
        """
        Alternative approach: Try sending form data instead of JSON
        """
        try:
            headers = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9',
                'origin': 'https://freednclist.com',
                'referer': 'https://freednclist.com/',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36'
            }
            
            # Try form data instead of JSON
            form_data = aiohttp.FormData()
            form_data.add_field('phone_number', phone_number)
            
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                connector=connector
            ) as session:
                async with session.post(
                    self.freednclist_url,
                    data=form_data,
                    headers=headers
                ) as response:
                    
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        
                        if 'application/json' in content_type:
                            data = await response.json()
                            logger.info(f"FreeDNCList form data API response for {phone_number}: {data}")
                            
                            is_dnc = data.get('is_dnc', False) or data.get('dnc_status', False)
                            dnc_source = data.get('source', 'freednclist')
                            
                            return {
                                "is_dnc": is_dnc,
                                "dnc_source": dnc_source,
                                "status": "dnc_listed" if is_dnc else "safe_to_call",
                                "notes": f"Checked against FreeDNCList.com (form data) - {'Listed' if is_dnc else 'Not listed'}"
                            }
                        else:
                            # Still getting HTML - log for debugging
                            html_content = await response.text()
                            logger.warning(f"FreeDNCList form data API still returned HTML for {phone_number}")
                            logger.warning(f"HTML content preview: {html_content[:500]}...")
                            
                            # For now, return a safe fallback since we can't parse the response
                            return {
                                "is_dnc": False,
                                "dnc_source": "freednclist_html_response",
                                "status": "api_unavailable",
                                "notes": "FreeDNCList API returned HTML instead of JSON - API may be down or changed"
                            }
                    else:
                        return {
                            "is_dnc": False,
                            "dnc_source": "freednclist_error",
                            "status": "api_error",
                            "notes": f"FreeDNCList form data API error: HTTP {response.status}"
                        }
                        
        except Exception as e:
            logger.error(f"FreeDNCList form data API error for {phone_number}: {e}")
            return {
                "is_dnc": False,
                "dnc_source": "freednclist_error",
                "status": "error",
                "notes": f"FreeDNCList form data API error: {str(e)}"
            }
    
    async def batch_check_dnc(self, phone_numbers: List[str]) -> Dict[str, list]:
        """
        Check multiple phone numbers against DNC lists using FreeDNCList.com API
        
        Args:
            phone_numbers: List of phone numbers to check
            
        Returns:
            Dict containing results for each phone number
        """
        results = []
        
        # Process in smaller batches to avoid overwhelming the API
        batch_size = 10  # Smaller batch size for FreeDNCList API
        for i in range(0, len(phone_numbers), batch_size):
            batch = phone_numbers[i:i + batch_size]
            
            # Create tasks for concurrent processing within the batch
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
            
            # Add delay between batches to be respectful to the FreeDNCList API
            if i + batch_size < len(phone_numbers):
                await asyncio.sleep(1.0)  # 1 second delay between batches
        
        return {"results": results}
    
    async def batch_check_freednclist_only(self, phone_numbers: List[str]) -> Dict[str, list]:
        """
        Check multiple phone numbers using ONLY FreeDNCList.com API (no FCC fallback)
        
        Args:
            phone_numbers: List of phone numbers to check
            
        Returns:
            Dict containing results for each phone number
        """
        results = []
        
        # Process in smaller batches to avoid overwhelming the API
        batch_size = 10  # Smaller batch size for FreeDNCList API
        for i in range(0, len(phone_numbers), batch_size):
            batch = phone_numbers[i:i + batch_size]
            
            # Create tasks for concurrent processing within the batch
            tasks = [self._check_freednclist_api(phone) for phone in batch]
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
            
            # Add delay between batches to be respectful to the FreeDNCList API
            if i + batch_size < len(phone_numbers):
                await asyncio.sleep(1.0)  # 1 second delay between batches
        
        return {"results": results}


# Global instance
dnc_service = DNCService()
