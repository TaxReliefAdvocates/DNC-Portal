#!/usr/bin/env python3
"""
Database consistency check script for DNC Portal
Run this to identify data issues before cleanup
"""

import os
import sys
import psycopg2
from datetime import datetime, timedelta

def get_db_connection():
    """Get database connection from environment variables"""
    try:
        # Try to get from environment variables
        db_url = os.getenv('DATABASE_URL')
        if db_url:
            return psycopg2.connect(db_url)
        
        # Fallback to individual variables
        return psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'do_not_call'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', ''),
            port=os.getenv('DB_PORT', '5432')
        )
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return None

def check_database_issues():
    """Check for various database inconsistencies"""
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print("🔍 DNC PORTAL DATABASE CONSISTENCY CHECK")
    print("=" * 50)
    
    # 1. Find stuck requests (approved but no propagation attempts)
    print("\n1️⃣ CHECKING: Approved requests with no propagation attempts")
    cursor.execute("""
        SELECT dr.id, dr.phone_e164, dr.status, dr.created_at, dr.decided_at
        FROM dnc_requests dr
        LEFT JOIN propagation_attempts pa ON dr.phone_e164 = pa.phone_e164 
            AND dr.organization_id = pa.organization_id
        WHERE dr.status = 'approved' 
            AND pa.id IS NULL
        ORDER BY dr.created_at DESC;
    """)
    
    stuck_requests = cursor.fetchall()
    if stuck_requests:
        print(f"❌ FOUND {len(stuck_requests)} approved requests with NO propagation attempts:")
        for req in stuck_requests:
            print(f"   - Request {req[0]}: {req[1]} (approved {req[4]})")
    else:
        print("✅ All approved requests have propagation attempts")
    
    # 2. Find orphaned propagation attempts
    print("\n2️⃣ CHECKING: Orphaned propagation attempts")
    cursor.execute("""
        SELECT pa.id, pa.phone_e164, pa.service_key, pa.status, pa.started_at
        FROM propagation_attempts pa
        LEFT JOIN dnc_requests dr ON pa.phone_e164 = dr.phone_e164 
            AND pa.organization_id = dr.organization_id
        WHERE dr.id IS NULL OR dr.status != 'approved'
        ORDER BY pa.started_at DESC;
    """)
    
    orphaned_attempts = cursor.fetchall()
    if orphaned_attempts:
        print(f"❌ FOUND {len(orphaned_attempts)} orphaned propagation attempts:")
        for attempt in orphaned_attempts:
            print(f"   - Attempt {attempt[0]}: {attempt[1]} ({attempt[2]}) - {attempt[3]} at {attempt[4]}")
    else:
        print("✅ No orphaned propagation attempts found")
    
    # 3. Find stuck pending attempts (older than 1 hour)
    print("\n3️⃣ CHECKING: Stuck pending attempts (older than 1 hour)")
    cursor.execute("""
        SELECT pa.id, pa.phone_e164, pa.service_key, pa.started_at,
               EXTRACT(EPOCH FROM (NOW() - pa.started_at))/3600 as hours_old
        FROM propagation_attempts pa
        WHERE pa.status = 'pending' 
            AND pa.started_at < NOW() - INTERVAL '1 hour'
        ORDER BY pa.started_at ASC;
    """)
    
    stuck_pending = cursor.fetchall()
    if stuck_pending:
        print(f"❌ FOUND {len(stuck_pending)} stuck pending attempts:")
        for attempt in stuck_pending:
            print(f"   - Attempt {attempt[0]}: {attempt[1]} ({attempt[2]}) - {attempt[4]:.1f} hours old")
    else:
        print("✅ No stuck pending attempts found")
    
    # 4. Find mismatched states (approved but systems show pending)
    print("\n4️⃣ CHECKING: Mismatched states (approved requests with pending attempts)")
    cursor.execute("""
        SELECT dr.id, dr.phone_e164, dr.status, 
               COUNT(pa.id) as attempt_count,
               COUNT(CASE WHEN pa.status = 'pending' THEN 1 END) as pending_count,
               COUNT(CASE WHEN pa.status = 'success' THEN 1 END) as success_count,
               COUNT(CASE WHEN pa.status = 'failed' THEN 1 END) as failed_count
        FROM dnc_requests dr
        LEFT JOIN propagation_attempts pa ON dr.phone_e164 = pa.phone_e164
            AND dr.organization_id = pa.organization_id
        WHERE dr.status = 'approved'
        GROUP BY dr.id, dr.phone_e164, dr.status
        HAVING COUNT(pa.id) != 5 OR COUNT(CASE WHEN pa.status = 'pending' THEN 1 END) > 0
        ORDER BY dr.created_at DESC;
    """)
    
    mismatched = cursor.fetchall()
    if mismatched:
        print(f"❌ FOUND {len(mismatched)} approved requests with issues:")
        for req in mismatched:
            print(f"   - Request {req[0]}: {req[1]}")
            print(f"     Total attempts: {req[3]}, Pending: {req[4]}, Success: {req[5]}, Failed: {req[6]}")
    else:
        print("✅ All approved requests have correct propagation state")
    
    # 5. Summary statistics
    print("\n5️⃣ SUMMARY STATISTICS")
    cursor.execute("SELECT COUNT(*) FROM dnc_requests WHERE status = 'pending'")
    pending_requests = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM dnc_requests WHERE status = 'approved'")
    approved_requests = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM propagation_attempts")
    total_attempts = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM propagation_attempts WHERE status = 'pending'")
    pending_attempts = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM propagation_attempts WHERE status = 'success'")
    success_attempts = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM propagation_attempts WHERE status = 'failed'")
    failed_attempts = cursor.fetchone()[0]
    
    print(f"📊 REQUEST STATS:")
    print(f"   - Pending requests: {pending_requests}")
    print(f"   - Approved requests: {approved_requests}")
    print(f"   - Total propagation attempts: {total_attempts}")
    print(f"   - Pending attempts: {pending_attempts}")
    print(f"   - Success attempts: {success_attempts}")
    print(f"   - Failed attempts: {failed_attempts}")
    
    # Calculate expected vs actual
    expected_attempts = approved_requests * 5
    print(f"   - Expected attempts (approved * 5): {expected_attempts}")
    print(f"   - Actual attempts: {total_attempts}")
    print(f"   - Difference: {total_attempts - expected_attempts}")
    
    conn.close()
    
    # Recommendations
    print("\n🎯 RECOMMENDATIONS:")
    if stuck_requests or orphaned_attempts or stuck_pending or mismatched:
        print("❌ DATABASE HAS ISSUES - Cleanup recommended")
        if stuck_pending:
            print("   - Clear stuck pending attempts")
        if orphaned_attempts:
            print("   - Remove orphaned propagation attempts")
        if stuck_requests:
            print("   - Reset approved requests that never propagated")
        print("   - Consider Option A: Full wipe and start fresh")
    else:
        print("✅ DATABASE LOOKS HEALTHY - No cleanup needed")

if __name__ == "__main__":
    check_database_issues()
