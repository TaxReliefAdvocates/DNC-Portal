#!/usr/bin/env python3

import requests
import json

# Test the DNC History API
url = "http://localhost:8000/api/v1/tenants/propagation/attempts/1"
headers = {
    "X-Org-Id": "1",
    "X-User-Id": "1", 
    "X-Role": "superadmin"
}

try:
    response = requests.get(url, headers=headers)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ API working! Found {len(data)} DNC history records")
        if data:
            print("Sample record:")
            print(json.dumps(data[0], indent=2))
        else:
            print("No DNC history records yet - this is expected for a new database")
    else:
        print(f"❌ API error: {response.text}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test the docs endpoint
try:
    docs_response = requests.get("http://localhost:8000/docs")
    if docs_response.status_code == 200:
        print("✅ Backend server is running and accessible!")
    else:
        print(f"❌ Docs endpoint error: {docs_response.status_code}")
except Exception as e:
    print(f"❌ Docs endpoint error: {e}")
