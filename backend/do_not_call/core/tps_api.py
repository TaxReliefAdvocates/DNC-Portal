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
        """Generate common formatting variants for US phone numbers.

        Many TPS queries are strict about formatting. We try a broad set:
        - raw digits (10 and 11 with leading 1)
        - (AAA)PPP-NNN and (AAA) PPP-NNN
        - AAA-PPP-NNN, AAA.PPP.NNN, AAA PPP NNN
        - E.164 (+1AAAAAAAAAA) and 1-AAA-PPP-NNN
        - original input as last resort
        """
        original = phone or ""
        digits_all = cls._digits_only(original)

        candidates: list[str] = []

        # If 11 digits with country code, include both forms
        if len(digits_all) == 11 and digits_all.startswith("1"):
            digits10 = digits_all[1:]
            candidates.append(digits_all)              # 1AAAAAAAAAA
            candidates.append("+" + digits_all)        # +1AAAAAAAAAA
        else:
            digits10 = digits_all

        if len(digits10) == 10:
            a, p, n = digits10[:3], digits10[3:6], digits10[6:]
            # Core formats
            candidates.extend([
                digits10,                     # AAAAAAAAAA
                f"({a}){p}-{n}",              # (AAA)PPP-NNN
                f"({a}) {p}-{n}",             # (AAA) PPP-NNN
                f"{a}-{p}-{n}",               # AAA-PPP-NNN
                f"{a}.{p}.{n}",               # AAA.PPP.NNN
                f"{a} {p} {n}",               # AAA PPP NNN
                f"+1{digits10}",              # +1AAAAAAAAAA
                f"1-{a}-{p}-{n}",            # 1-AAA-PPP-NNN
                f"1{digits10}",               # 1AAAAAAAAAA
            ])
        # Fallback to original input
        candidates.append(original)

        # Ensure uniqueness preserving order
        seen: set[str] = set()
        ordered: list[str] = []
        for v in candidates:
            if v and v not in seen:
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


