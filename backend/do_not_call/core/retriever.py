from typing import List
from loguru import logger
from .crm_clients.base import BaseCRMClient
from .api.v1.tenants import ingest_samples  # for typing reference only


async def collect_daily_sample(crm_client: BaseCRMClient, limit: int = 10000) -> List[str]:
    try:
        numbers = await crm_client.fetch_daily_unique_numbers(limit=limit)
        # normalize to E.164 digits-only if needed
        cleaned: List[str] = []
        for n in numbers:
            digits = ''.join(ch for ch in str(n) if ch.isdigit())
            if len(digits) == 10:
                cleaned.append(digits)
            elif len(digits) == 11 and digits.startswith('1'):
                cleaned.append(digits[1:])
        return list(dict.fromkeys(cleaned))[:limit]
    except Exception as e:
        logger.error(f"Daily sample collection failed: {e}")
        return []


# Dataverse helpers (lightweight)
import httpx
from typing import Any, Dict, Optional
from ..config import settings


async def dataverse_get_token() -> Optional[str]:
    if not (settings.DATAVERSE_TENANT_ID and settings.DATAVERSE_CLIENT_ID and settings.DATAVERSE_CLIENT_SECRET and settings.DATAVERSE_BASE_URL):
        return None
    token_url = f"https://login.microsoftonline.com/{settings.DATAVERSE_TENANT_ID}/oauth2/v2.0/token"
    scope = f"{settings.DATAVERSE_BASE_URL.rstrip('/')}/.default"
    data = {
        "client_id": settings.DATAVERSE_CLIENT_ID,
        "client_secret": settings.DATAVERSE_CLIENT_SECRET,
        "grant_type": "client_credentials",
        "scope": scope,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(token_url, data=data)
        r.raise_for_status()
        js = r.json()
        return js.get("access_token")


async def dataverse_fetch_entity_records(entity_logical_name: str, select: Optional[List[str]] = None, top: int = 1000) -> List[Dict[str, Any]]:
    token = await dataverse_get_token()
    if not token:
        return []
    base = settings.DATAVERSE_BASE_URL.rstrip('/')
    meta_url = f"{base}/api/data/v9.2/EntityDefinitions(LogicalName='{entity_logical_name}')?$select=EntitySetName"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        mr = await client.get(meta_url, headers=headers)
        mr.raise_for_status()
        entity_set = mr.json().get("EntitySetName")
        if not entity_set:
            return []
        q = []
        if select:
            q.append(f"$select={','.join(select)}")
        if top:
            q.append(f"$top={int(top)}")
        query = ("&".join(q)) if q else ""
        url = f"{base}/api/data/v9.2/{entity_set}{'?' + query if query else ''}"
        res = await client.get(url, headers=headers)
        res.raise_for_status()
        data = res.json()
        return data.get('value', [])


