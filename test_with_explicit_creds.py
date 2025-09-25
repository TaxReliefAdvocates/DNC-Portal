#!/usr/bin/env python3
"""
Test provider endpoints with explicit credentials to verify they work
"""
import asyncio
import httpx
import json

# Test phone number
TEST_PHONE = "5618189087"
BASE_URL = "https://dnc-backend-bb96.onrender.com"

# Credentials from render.yaml
CONVOSO_AUTH_TOKEN = "swai20svbj229p1f3cozei7uxbsbvyne"
YTEL_USER = "103"
YTEL_PASSWORD = "bHSQPgE7J6nLzX"
GENESYS_CLIENT_ID = "efc1134d-8252-4aea-a995-47b1dc0c5fba"
GENESYS_CLIENT_SECRET = "o2Tqu6dXnLKvI3UAg5iRkzb6MwGvXrlUrzO1kaGguCY"
LOGICS_BASIC_AUTH_B64 = "NDkxN2ZhMGNlNDY5NDUyOWE5Yjk3ZWFkMWE2MGM5MzI6YTc3YThlNTAtZTllYS00MTg1LThiMGUtYzI0YjQ2OGIyYTM4"

async def test_with_explicit_creds():
    """Test endpoints with explicit credentials"""
    print("🔍 Testing Provider Endpoints with Explicit Credentials")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test Convoso with explicit token
        print("\n🧪 Testing Convoso with explicit auth_token...")
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/convoso/search-dnc",
                json={"phone_number": TEST_PHONE, "phone_code": "1"},
                params={"auth_token": CONVOSO_AUTH_TOKEN}
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✅ SUCCESS! Convoso works with explicit token")
                result = response.json()
                print(f"   📄 Response: {json.dumps(result, indent=2)}")
            else:
                print("   ❌ FAILED")
                print(f"   📄 Response: {response.json()}")
        except Exception as e:
            print(f"   🚨 Exception: {e}")
        
        # Test Ytel with explicit credentials
        print("\n🧪 Testing Ytel with explicit credentials...")
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/ytel/search-dnc",
                json={"phone_number": TEST_PHONE, "phone_code": "1"},
                params={"user": YTEL_USER, "password": YTEL_PASSWORD}
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✅ SUCCESS! Ytel works with explicit credentials")
                result = response.json()
                print(f"   📄 Response: {json.dumps(result, indent=2)}")
            else:
                print("   ❌ FAILED")
                print(f"   📄 Response: {response.json()}")
        except Exception as e:
            print(f"   🚨 Exception: {e}")
        
        # Test Genesys with explicit credentials
        print("\n🧪 Testing Genesys with explicit credentials...")
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/genesys/auth",
                json={},
                params={"client_id": GENESYS_CLIENT_ID, "client_secret": GENESYS_CLIENT_SECRET}
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✅ SUCCESS! Genesys works with explicit credentials")
                result = response.json()
                print(f"   📄 Response: {json.dumps(result, indent=2)}")
            else:
                print("   ❌ FAILED")
                print(f"   📄 Response: {response.json()}")
        except Exception as e:
            print(f"   🚨 Exception: {e}")
        
        # Test Logics with explicit auth
        print("\n🧪 Testing Logics with explicit auth...")
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/logics/search-by-phone",
                json={"phone_number": TEST_PHONE},
                params={"basic_auth_b64": LOGICS_BASIC_AUTH_B64}
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✅ SUCCESS! Logics works with explicit auth")
                result = response.json()
                print(f"   📄 Response: {json.dumps(result, indent=2)}")
            else:
                print("   ❌ FAILED")
                print(f"   📄 Response: {response.json()}")
        except Exception as e:
            print(f"   🚨 Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_with_explicit_creds())
