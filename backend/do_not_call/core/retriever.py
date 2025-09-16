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


