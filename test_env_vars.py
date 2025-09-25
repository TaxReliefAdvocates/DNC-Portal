#!/usr/bin/env python3
"""
Test script to check environment variables on the deployed backend
"""
import asyncio
import httpx
import json

BASE_URL = "https://dnc-backend-bb96.onrender.com"

async def test_env_vars():
    """Test environment variables by calling endpoints that should work with env vars"""
    print("🔍 Testing Environment Variables on Deployed Backend")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test endpoints that should work with environment variables
        tests = [
            {
                "name": "RingCentral Auth (should work with JWT)",
                "url": f"{BASE_URL}/api/v1/ringcentral/auth",
                "method": "POST",
                "data": {}
            },
            {
                "name": "Convoso Auth (should work with CONVOSO_AUTH_TOKEN)",
                "url": f"{BASE_URL}/api/v1/convoso/auth",
                "method": "POST",
                "data": {}
            },
            {
                "name": "Genesys Auth (should work with GENESYS_CLIENT_ID/SECRET)",
                "url": f"{BASE_URL}/api/v1/genesys/auth",
                "method": "POST",
                "data": {}
            }
        ]
        
        for test in tests:
            print(f"\n🧪 Testing: {test['name']}")
            try:
                response = await client.post(test['url'], json=test['data'])
                print(f"   Status: {response.status_code}")
                
                if response.status_code == 200:
                    print("   ✅ SUCCESS - Environment variables are working!")
                    result = response.json()
                    if isinstance(result, dict):
                        print(f"   📄 Response: {json.dumps(result, indent=2)}")
                    else:
                        print(f"   📄 Response: {result}")
                else:
                    print("   ❌ FAILED - Environment variables not working")
                    result = response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
                    print(f"   📄 Error: {result}")
                    
            except Exception as e:
                print(f"   🚨 Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_env_vars())
