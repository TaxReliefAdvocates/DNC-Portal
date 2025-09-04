from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.models import (
    Organization, OrganizationCreate, OrganizationResponse,
    User, UserCreate, UserResponse,
    OrgService, OrgServiceCreate, OrgServiceResponse,
    DNCEntry, DNCEntryCreate, DNCEntryResponse,
    RemovalJob, RemovalJobCreate, RemovalJobResponse,
    RemovalJobItem, RemovalJobItemCreate, RemovalJobItemResponse,
    CRMDNCSample,
)

router = APIRouter()


# Organizations
@router.post("/organizations", response_model=OrganizationResponse)
def create_org(payload: OrganizationCreate, db: Session = Depends(get_db)):
    if db.query(Organization).filter_by(slug=payload.slug).first():
        raise HTTPException(status_code=400, detail="Organization slug already exists")
    org = Organization(name=payload.name, slug=payload.slug)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.get("/organizations", response_model=list[OrganizationResponse])
def list_orgs(db: Session = Depends(get_db)):
    return db.query(Organization).order_by(Organization.id.desc()).all()


# Users
@router.post("/users", response_model=UserResponse)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=payload.email).first():
        raise HTTPException(status_code=400, detail="User email already exists")
    user = User(email=payload.email, name=payload.name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.id.desc()).all()


# Org Services
@router.post("/org-services", response_model=OrgServiceResponse)
def create_org_service(payload: OrgServiceCreate, db: Session = Depends(get_db)):
    svc = OrgService(
        organization_id=payload.organization_id,
        service_key=payload.service_key,
        display_name=payload.display_name,
        is_active=payload.is_active,
        credentials=payload.credentials,
        settings=payload.settings,
    )
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc


@router.get("/org-services/{organization_id}", response_model=list[OrgServiceResponse])
def list_org_services(organization_id: int, db: Session = Depends(get_db)):
    return db.query(OrgService).filter_by(organization_id=organization_id).all()


# DNC Entries
@router.post("/dnc-entries", response_model=DNCEntryResponse)
def create_dnc_entry(payload: DNCEntryCreate, db: Session = Depends(get_db)):
    entry = DNCEntry(**payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/dnc-entries/{organization_id}", response_model=list[DNCEntryResponse])
def list_dnc_entries(organization_id: int, db: Session = Depends(get_db)):
    return db.query(DNCEntry).filter_by(organization_id=organization_id).order_by(DNCEntry.id.desc()).limit(500).all()


# Jobs + Items
@router.post("/jobs", response_model=RemovalJobResponse)
def create_job(payload: RemovalJobCreate, db: Session = Depends(get_db)):
    job = RemovalJob(**payload.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/job-items", response_model=RemovalJobItemResponse)
def create_job_item(payload: RemovalJobItemCreate, db: Session = Depends(get_db)):
    item = RemovalJobItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/jobs/{organization_id}", response_model=list[RemovalJobResponse])
def list_jobs(organization_id: int, db: Session = Depends(get_db)):
    return db.query(RemovalJob).filter_by(organization_id=organization_id).order_by(RemovalJob.id.desc()).all()


@router.post("/dnc-samples/ingest/{organization_id}")
def ingest_samples(organization_id: int, rows: list[dict], db: Session = Depends(get_db)):
    """Bulk ingest up to 10k rows per call. Rows: {phone_e164, in_national_dnc, in_org_dnc, crm_source?, notes?}."""
    to_add: list[CRMDNCSample] = []
    from datetime import datetime
    sample_date = datetime.utcnow()
    for r in rows[:10000]:
        phone = str(r.get("phone_e164", ""))
        if not phone:
            continue
        to_add.append(CRMDNCSample(
            organization_id=organization_id,
            sample_date=sample_date,
            phone_e164=phone,
            in_national_dnc=bool(r.get("in_national_dnc", False)),
            in_org_dnc=bool(r.get("in_org_dnc", False)),
            crm_source=r.get("crm_source"),
            notes=r.get("notes"),
        ))
    if to_add:
        db.bulk_save_objects(to_add)
        db.commit()
    return {"ingested": len(to_add), "sample_date": sample_date.isoformat()}


@router.get("/dnc-samples/{organization_id}")
def query_samples(organization_id: int, only_gaps: bool = True, limit: int = 1000, db: Session = Depends(get_db)):
    q = db.query(CRMDNCSample).filter(CRMDNCSample.organization_id == organization_id)
    if only_gaps:
        q = q.filter(CRMDNCSample.in_national_dnc.is_(True), CRMDNCSample.in_org_dnc.is_(False))
    rows = q.order_by(CRMDNCSample.sample_date.desc()).limit(min(10000, limit)).all()
    return [{
        "id": r.id,
        "phone_e164": r.phone_e164,
        "in_national_dnc": r.in_national_dnc,
        "in_org_dnc": r.in_org_dnc,
        "sample_date": r.sample_date.isoformat(),
        "crm_source": r.crm_source,
        "notes": r.notes,
    } for r in rows]

