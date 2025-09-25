#!/usr/bin/env python3
"""
Comprehensive test script for all provider DNC endpoints
Tests both with and without explicit credentials
"""
import asyncio
import httpx
import json
from datetime import datetime

# Test phone number
TEST_PHONE = "5618189087"
BASE_URL = "https://dnc-backend-bb96.onrender.com"

async def test_endpoint(client, method, url, data=None, params=None, headers=None, description=""):
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
            "url": str(response.url),
            "description": description
        }
    except Exception as e:
        return {
            "status_code": 0,
            "success": False,
            "error": str(e),
            "url": url,
            "description": description
        }

async def test_all_providers():
    """Test all provider endpoints comprehensively"""
    print(f"🔍 Comprehensive DNC Provider Test Suite")
    print(f"📞 Test Phone Number: {TEST_PHONE}")
    print(f"🌐 Base URL: {BASE_URL}")
    print(f"⏰ Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        results = {}
        
        # Test endpoints with different scenarios
        endpoints = [
            # RingCentral Tests
            {
                "name": "RingCentral Auth (Auto JWT)",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/ringcentral/auth",
                "data": {},
                "description": "Should work with environment JWT"
            },
            {
                "name": "RingCentral Add DNC",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/ringcentral/add-dnc",
                "data": {"phone_number": TEST_PHONE, "phone_code": "1"},
                "description": "Should work with auto JWT"
            },
            {
                "name": "RingCentral List All DNC",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/ringcentral/list-all-dnc",
                "data": {},
                "description": "Should work with auto JWT"
            },
            
            # Convoso Tests
            {
                "name": "Convoso Auth (Auto Token)",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/convoso/auth",
                "data": {},
                "description": "Should work with environment token"
            },
            {
                "name": "Convoso Search DNC (Auto Token)",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/convoso/search-dnc",
                "data": {"phone_number": TEST_PHONE, "phone_code": "1"},
                "description": "Should work with environment token"
            },
            {
                "name": "Convoso Search By Phone (Auto Token)",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/convoso/search-by-phone",
                "data": {"phone_number": TEST_PHONE},
                "description": "Should work with environment token"
            },
            
            # Ytel Tests
            {
                "name": "Ytel Search DNC (Auto Creds)",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/ytel/search-dnc",
                "data": {"phone_number": TEST_PHONE, "phone_code": "1"},
                "description": "Should work with environment credentials"
            },
            {
                "name": "Ytel Add DNC (Auto Creds)",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/ytel/add-dnc",
                "data": {"phone_number": TEST_PHONE, "phone_code": "1"},
                "description": "Should work with environment credentials"
            },
            
            # Genesys Tests
            {
                "name": "Genesys Auth (Auto Creds)",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/genesys/auth",
                "data": {},
                "description": "Should work with environment credentials"
            },
            {
                "name": "Genesys List All DNC (Auto Token)",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/genesys/list-all-dnc",
                "data": {},
                "description": "Should work with auto token"
            },
            
            # Logics Tests
            {
                "name": "Logics Search By Phone (Auto Auth)",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/logics/search-by-phone",
                "data": {"phone_number": TEST_PHONE},
                "description": "Should work with environment auth"
            },
            {
                "name": "Logics Update Case (Auto Auth)",
                "method": "POST",
                "url": f"{BASE_URL}/api/v1/logics/update-case",
                "data": {"case_id": 12345, "status_id": 57},
                "description": "Should work with environment auth"
            },
            
            # FreeDNC Test
            {
                "name": "FreeDNC Check",
                "method": "POST",
                "url": f"{BASE_URL}/api/check_number",
                "data": {"phone_number": TEST_PHONE},
                "description": "Should always work"
            }
        ]
        
        # Run all tests
        for endpoint in endpoints:
            print(f"\n🧪 Testing: {endpoint['name']}")
            print(f"   📝 {endpoint['description']}")
            print(f"   🔗 {endpoint['method']} {endpoint['url']}")
            
            result = await test_endpoint(
                client,
                endpoint['method'],
                endpoint['url'],
                endpoint.get('data'),
                endpoint.get('params'),
                description=endpoint['description']
            )
            
            results[endpoint['name']] = result
            
            # Print result
            if result['success']:
                print(f"   ✅ Status: {result['status_code']}")
                if isinstance(result['response'], dict):
                    # Pretty print JSON response (truncate long responses)
                    response_str = json.dumps(result['response'], indent=2)
                    if len(response_str) > 500:
                        response_str = response_str[:500] + "... (truncated)"
                    print(f"   📄 Response: {response_str}")
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
        print("📊 COMPREHENSIVE SUMMARY")
        print("=" * 80)
        
        successful = sum(1 for r in results.values() if r['success'])
        total = len(results)
        
        print(f"✅ Successful: {successful}/{total}")
        print(f"❌ Failed: {total - successful}/{total}")
        
        # Group by provider
        providers = {
            "RingCentral": [],
            "Convoso": [],
            "Ytel": [],
            "Genesys": [],
            "Logics": [],
            "FreeDNC": []
        }
        
        for name, result in results.items():
            for provider in providers:
                if provider.lower() in name.lower():
                    providers[provider].append((name, result))
                    break
        
        print("\n📋 PROVIDER BREAKDOWN:")
        for provider, tests in providers.items():
            if tests:
                success_count = sum(1 for _, result in tests if result['success'])
                total_count = len(tests)
                status = "✅" if success_count == total_count else "⚠️" if success_count > 0 else "❌"
                print(f"   {status} {provider}: {success_count}/{total_count} working")
                
                for test_name, result in tests:
                    test_status = "✅" if result['success'] else "❌"
                    print(f"      {test_status} {test_name}")
        
        if successful < total:
            print("\n🚨 FAILED ENDPOINTS:")
            for name, result in results.items():
                if not result['success']:
                    error_msg = result.get('error', f"HTTP {result['status_code']}")
                    if isinstance(result.get('response'), dict) and 'detail' in result['response']:
                        error_msg = result['response']['detail']
                    print(f"   • {name}: {error_msg}")
        
        print(f"\n🎯 RECOMMENDATIONS:")
        if successful == total:
            print("   🎉 All endpoints are working perfectly!")
        else:
            print("   🔧 Check environment variables in render.yaml")
            print("   🔄 Consider redeploying if env vars were recently updated")
            print("   📝 Verify provider credentials are correct")
        
        return results

if __name__ == "__main__":
    asyncio.run(test_all_providers())
