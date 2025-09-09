#!/usr/bin/env python3
"""
Seed script to populate the database with sample data for testing
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone
import random

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from do_not_call.core.database import get_db, create_tables
from do_not_call.core.models import (
    PhoneNumber, CRMStatus,
    Organization, User, OrgUser,
    ServiceCatalog, OrgService,
    DNCEntry, RemovalJob, RemovalJobItem,
)
from do_not_call.core.types import CRMSystem, CRMStatusType
from do_not_call.config import settings


def seed_database():
    """Seed the database with sample data"""
    print("🌱 Seeding database with sample data...")
    
    # Create tables first
    print("📋 Creating database tables...")
    create_tables()
    
    db = next(get_db())
    try:
        # Organizations and Users
        org = Organization(name="Test Org", slug="test-org")
        db.add(org)
        user = User(email="admin@example.com", name="Admin User", role="owner")
        db.add(user)
        db.flush()
        db.add(OrgUser(organization_id=org.id, user_id=user.id, role="owner"))

        # Service catalog + org services
        services = [
            ("convoso", "Convoso"),
            ("ytel", "Ytel"),
            ("ringcentral", "Ring Central"),
            ("genesys", "Genesys"),
            ("logics", "Logics"),
        ]
        for key, name in services:
            if not db.query(ServiceCatalog).filter_by(key=key).first():
                db.add(ServiceCatalog(key=key, name=name))
        db.flush()
        for key, _ in services:
            if not db.query(OrgService).filter_by(organization_id=org.id, service_key=key).first():
                db.add(OrgService(organization_id=org.id, service_key=key, is_active=True))

        # Sample phone numbers
        sample_phone_numbers = [
            "+15551234567",
            "+15551234568", 
            "+15551234569",
            "+15551234570",
            "+15551234571",
            "+15551234572",
            "+15551234573",
            "+15551234574",
            "+15551234575",
            "+15551234576",
            "+15551234577",
            "+15551234578",
            "+15551234579",
            "+15551234580",
            "+15551234581"
        ]
        
        # Create phone numbers
        phone_numbers = []
        for i, phone in enumerate(sample_phone_numbers):
            phone_number = PhoneNumber(
                phone_number=phone,
                status="active",
                notes=f"Sample phone number {i+1}",
                created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))
            )
            db.add(phone_number)
            phone_numbers.append(phone_number)
        
        db.commit()
        print(f"✅ Created {len(phone_numbers)} phone numbers")
        
        # Create CRM status records
        crm_systems = [
            CRMSystem.trackdrive, 
            CRMSystem.irslogics, 
            CRMSystem.listflex, 
            CRMSystem.retriever,
            CRMSystem.everflow
        ]
        status_types = [CRMStatusType.pending, CRMStatusType.processing, CRMStatusType.completed, CRMStatusType.failed]
        
        crm_statuses = []
        for phone_number in phone_numbers:
            # Create status for each CRM system
            for crm_system in crm_systems:
                status = random.choice(status_types)
                crm_status = CRMStatus(
                    phone_number_id=phone_number.id,
                    crm_system=crm_system.value,
                    status=status.value,
                    error_message=None if status != CRMStatusType.failed else "Sample error message",
                    retry_count=random.randint(0, 3) if status == CRMStatusType.failed else 0,
                    created_at=phone_number.created_at,
                    updated_at=datetime.utcnow() - timedelta(hours=random.randint(1, 24))
                )
                db.add(crm_status)
                crm_statuses.append(crm_status)
        
        db.commit()

        # Seed DNC entries for the org
        for phone in sample_phone_numbers[:5]:
            db.add(DNCEntry(
                organization_id=org.id,
                phone_e164=phone.replace("+", ""),
                reason="customer opt-out",
                source="manual",
                created_by_user_id=user.id,
            ))
        db.commit()

        # Seed a removal job with items
        job = RemovalJob(organization_id=org.id, submitted_by_user_id=user.id, notes="Initial test job", total=3, status="pending")
        db.add(job)
        db.flush()
        for phone in sample_phone_numbers[:3]:
            db.add(RemovalJobItem(job_id=job.id, phone_e164=phone.replace("+", ""), status="pending"))
        db.commit()
        print(f"✅ Created {len(crm_statuses)} CRM status records")
        
        # Print summary
        print("\n📊 Database Summary:")
        print(f"   • Phone Numbers: {len(phone_numbers)}")
        print(f"   • CRM Status Records: {len(crm_statuses)}")
        print(f"   • Organizations: 1, Users: 1, OrgServices: {len(services)}")
        
        # Status breakdown
        status_counts = {}
        for status in crm_statuses:
            status_counts[status.status] = status_counts.get(status.status, 0) + 1
        
        print("   • Status Breakdown:")
        for status, count in status_counts.items():
            print(f"     - {status}: {count}")
        
        print("\n🎉 Database seeding completed successfully!")
        
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
