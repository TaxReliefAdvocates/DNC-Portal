#!/usr/bin/env python3
"""
Test script for all provider DNC search endpoints
"""
import asyncio
import httpx
import json
from datetime import datetime

# Test phone number
TEST_PHONE = "5618189087"
BASE_URL = "https://dnc-backend-bb96.onrender.com"

async def test_endpoint(client, method, url, data=None, params=None, headers=None):
    """Test a single endpoint and return results"""
    try:
        if method.upper() == "GET":
            response = await client.get(url, params=params, headers=headers)
        elif method.upper() == "POST":
            response = await client.post(url, json=data, params=params, headers=headers)
        else:
            return {"error": f"Unsupported method: {method}"}
        
        return {
            "status_code": response.status_code,
            "success": response.status_code < 400,
            "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
            "url": str(response.url)
        }
    except Exception as e:
        return {
            "status_code": 0,
            "success": False,
            "error": str(e),
            "url": url
        }

async def test_all_providers():
    """Test all provider search endpoints"""
    print(f"🔍 Testing DNC Provider Search Endpoints")
    print(f"📞 Test Phone Number: {TEST_PHONE}")
    print(f"🌐 Base URL: {BASE_URL}")
    print("=" * 80)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        results = {}
        
        # Test endpoints
        endpoints = [
            # RingCentral
            {
                "name": "RingCentral Auth",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/ringcentral/auth",
                "data": {}
            },
            {
                "name": "RingCentral Search (Coming Soon)",
                "method": "POST", 
                "url": f"{BASE_URL}/api/v1/ringcentral/search-by-phone-coming-soon",
                "data": {"phone_number": TEST_PHONE, "phone_code": "1"}
            },
            
            # Convoso
            {
                "name": "Convoso Search DNC",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/convoso/search-dnc",
                "data": {"phone_number": TEST_PHONE, "phone_code": "1"}
            },
            {
                "name": "Convoso Search By Phone",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/convoso/search-by-phone",
                "data": {"phone_number": TEST_PHONE}
            },
            
            # Ytel
            {
                "name": "Ytel Search DNC",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/ytel/search-dnc",
                "data": {"phone_number": TEST_PHONE, "phone_code": "1"}
            },
            
            # Genesys
            {
                "name": "Genesys Auth",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/genesys/auth",
                "data": {}
            },
            {
                "name": "Genesys Search (Coming Soon)",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/genesys/search-dnc-coming-soon",
                "data": {"phone_number": TEST_PHONE, "phone_code": "1"}
            },
            
            # Logics
            {
                "name": "Logics Search By Phone",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/logics/search-by-phone",
                "data": {"phone_number": TEST_PHONE}
            },
            
            # FreeDNC
            {
                "name": "FreeDNC Check",
                "method": "POST",
                "url": f"{BASE_URL}/api/check_number",
                "data": {"phone_number": TEST_PHONE}
            }
        ]
        
        # Run all tests
        for endpoint in endpoints:
            print(f"\n🧪 Testing: {endpoint['name']}")
            print(f"   {endpoint['method']} {endpoint['url']}")
            
            result = await test_endpoint(
                client,
                endpoint['method'],
                endpoint['url'],
                endpoint.get('data'),
                endpoint.get('params')
            )
            
            results[endpoint['name']] = result
            
            # Print result
            if result['success']:
                print(f"   ✅ Status: {result['status_code']}")
                if isinstance(result['response'], dict):
                    # Pretty print JSON response
                    print(f"   📄 Response: {json.dumps(result['response'], indent=2)}")
                else:
                    print(f"   📄 Response: {result['response']}")
            else:
                print(f"   ❌ Status: {result['status_code']}")
                if 'error' in result:
                    print(f"   🚨 Error: {result['error']}")
                else:
                    print(f"   📄 Response: {result['response']}")
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        
        successful = sum(1 for r in results.values() if r['success'])
        total = len(results)
        
        print(f"✅ Successful: {successful}/{total}")
        print(f"❌ Failed: {total - successful}/{total}")
        
        if successful < total:
            print("\n🚨 Failed Endpoints:")
            for name, result in results.items():
                if not result['success']:
                    print(f"   • {name}: {result.get('error', 'HTTP ' + str(result['status_code']))}")
        
        return results

if __name__ == "__main__":
    asyncio.run(test_all_providers())
