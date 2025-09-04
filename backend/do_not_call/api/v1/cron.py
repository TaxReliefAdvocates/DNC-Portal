from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from loguru import logger

from ...core.database import get_db
from ...core.models import CRMDNCSample, DNCEntry
from ...core.dnc_service import dnc_service

router = APIRouter()


@router.post("/daily-sample/{organization_id}")
async def run_daily_sample(organization_id: int, numbers: list[str], db: Session = Depends(get_db)):
    """Accept pre-fetched unique numbers for the day, enrich with national/org DNC flags, and store."""
    if not numbers:
        raise HTTPException(status_code=400, detail="numbers list is required")

    sample_date = datetime.utcnow()
    rows: list[CRMDNCSample] = []
    # Preload org DNC set for quick lookup
    org_dnc_set = {r.phone_e164 for r in db.query(DNCEntry.phone_e164).filter(DNCEntry.organization_id == organization_id, DNCEntry.active.is_(True)).all()}

    count = 0
    for phone in numbers[:10000]:
        digits = ''.join(ch for ch in str(phone) if ch.isdigit())
        if len(digits) == 11 and digits.startswith('1'):
            digits = digits[1:]
        if len(digits) != 10:
            continue
        # National DNC check via FreeDNCList flow
        status = await dnc_service.check_federal_dnc(digits)
        in_national = bool(status.get("is_dnc"))
        in_org = digits in org_dnc_set
        rows.append(CRMDNCSample(
            organization_id=organization_id,
            sample_date=sample_date,
            phone_e164=digits,
            in_national_dnc=in_national,
            in_org_dnc=in_org,
            crm_source="daily",
        ))
        count += 1

    if rows:
        db.bulk_save_objects(rows)
        db.commit()
    logger.info(f"Daily sample stored: org={organization_id}, rows={len(rows)}")
    return {"ingested": len(rows), "sample_date": sample_date.isoformat()}


