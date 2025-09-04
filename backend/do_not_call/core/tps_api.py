import aiohttp
import ssl
import certifi
from typing import List, Dict, Any, Optional
from loguru import logger
import os
from do_not_call.config import settings


class TPSApiClient:
    """Client for TPS public API (FindCaseByPhone, CaseInfo)."""

    def __init__(self, base_url: str = "https://tps.logiqs.com/publicapi"):
        self.base_url = base_url.rstrip('/')
        self.verify_ssl_default = settings.TPS_API_VERIFY_SSL
        self.ssl_context_verified = ssl.create_default_context(cafile=certifi.where())

    @staticmethod
    def _digits_only(phone: str) -> str:
        return "".join(ch for ch in (phone or "") if ch.isdigit())

    @classmethod
    def _phone_variants(cls, phone: str) -> list[str]:
        digits = cls._digits_only(phone)
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        variants = []
        if len(digits) == 10:
            area, pre, line = digits[:3], digits[3:6], digits[6:]
            variants.append(f"({area}){pre}-{line}")
            variants.append(f"({area}) {pre}-{line}")
            variants.append(f"{area}-{pre}-{line}")
            variants.append(digits)
        else:
            variants.append(phone)
        # Ensure uniqueness preserving order
        seen = set()
        ordered = []
        for v in variants:
            if v not in seen:
                seen.add(v)
                ordered.append(v)
        return ordered
    async def find_cases_by_phone(self, phone: str) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/V3/Find/FindCaseByPhone"
        last_error: Optional[Exception] = None
        for variant in self._phone_variants(phone):
            params = {"phone": variant}
            data: Optional[Dict[str, Any]] = None
            try:
                connector = aiohttp.TCPConnector(ssl=self.ssl_context_verified if self.verify_ssl_default else False)
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get(url, params=params, timeout=30) as resp:
                        text = await resp.text()
                        data = await resp.json(content_type=None)
            except Exception as e:
                last_error = e
                if "CERTIFICATE_VERIFY_FAILED" in str(e):
                    logger.warning("TPS find_cases_by_phone SSL verify failed; retrying without verification")
                    connector = aiohttp.TCPConnector(ssl=False)
                    async with aiohttp.ClientSession(connector=connector) as session:
                        async with session.get(url, params=params, timeout=30) as resp:
                            text = await resp.text()
                            data = await resp.json(content_type=None)
                else:
                    continue

            if data and data.get("Success") and data.get("Data"):
                return data.get("Data", [])

        if last_error:
            logger.warning(f"TPS find by phone unsuccessful after variants; last error: {last_error}")
        return []

    async def get_case_info(self, case_id: int, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        # API versioned path requires apikey query string
        url = f"{self.base_url}/2020-02-22/cases/caseinfo"
        params = {"CaseID": str(case_id)}
        if not api_key:
            api_key = settings.TPS_API_KEY
        if api_key:
            params["apikey"] = api_key
        data: Optional[Dict[str, Any]] = None
        try:
            connector = aiohttp.TCPConnector(ssl=self.ssl_context_verified if self.verify_ssl_default else False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, params=params, timeout=30) as resp:
                    text = await resp.text()
                    data = await resp.json(content_type=None)
        except Exception as e:
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                logger.warning("TPS get_case_info SSL verify failed; retrying without verification")
                connector = aiohttp.TCPConnector(ssl=False)
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get(url, params=params, timeout=30) as resp:
                        text = await resp.text()
                        try:
                            data = await resp.json(content_type=None)
                        except Exception:
                            logger.error(f"TPS case info non-JSON: {text[:200]}")
                            return None
            else:
                logger.error(f"TPS case info error: {e}")
                return None
        if data and data.get("status") == "success":
            return data.get("data")
        return None


tps_api = TPSApiClient()


