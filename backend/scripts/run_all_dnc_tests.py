import os
import sys
import asyncio
from typing import Any, Dict, Optional
from dotenv import load_dotenv
import json
import pathlib

# Ensure project root is on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

import httpx
from httpx import ASGITransport

from app.main import app


PHONE_NUMBER = os.getenv("TEST_PHONE_NUMBER", "5618189087")
PHONE_CODE = os.getenv("TEST_PHONE_CODE", "1")


def env(key: str, default: Optional[str] = None) -> Optional[str]:
	val = os.getenv(key)
	return val if val not in (None, "") else default


def pp(title: str, data: Any):
	print(f"\n=== {title} ===")
	try:
		print(json.dumps(data, indent=2))
	except Exception:
		print(str(data))


async def call(client: httpx.AsyncClient, method: str, url: str, *, json_body: Optional[Dict] = None) -> Dict:
	try:
		resp = await client.request(method, url, json=json_body)
		content_type = resp.headers.get("content-type", "")
		if content_type.startswith("application/json"):
			return {"status": resp.status_code, "json": resp.json()}
		return {"status": resp.status_code, "text": resp.text}
	except Exception as e:
		return {"error": str(e)}


async def run():
	# Load env from backend/.env first (works when run from repo root or backend)
	backend_env = ROOT / ".env"
	if backend_env.exists():
		load_dotenv(backend_env)
	# Also load from current working directory .env (optional override)
	load_dotenv()
	transport = ASGITransport(app=app)
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
		# Ytel
		y_user = env("YTEL_USER")
		y_pass = env("YTEL_PASSWORD") or env("YTEL_PASS")
		query = f"?user={y_user}&password={y_pass}" if y_user and y_pass else ""
		pp("Ytel add-dnc", await call(client, "POST", f"/api/v1/ytel/add-dnc{query}", json_body={"phone_number": PHONE_NUMBER, "campaign_id": env("YTEL_CAMPAIGN_ID")}))
		pp("Ytel search-dnc", await call(client, "POST", f"/api/v1/ytel/search-dnc{query}", json_body={"phone_number": PHONE_NUMBER}))
		pp("Ytel upload-dnc", await call(client, "POST", f"/api/v1/ytel/upload-dnc{query}", json_body={
			"phone_number": PHONE_NUMBER,
			"list_id": env("YTEL_LIST_ID"),
			"first_name": env("YTEL_FIRST_NAME", "Reactivated"),
			"last_name": env("YTEL_LAST_NAME", "Lead"),
		}))
		pp("Ytel list-all-dnc (coming soon)", await call(client, "POST", "/api/v1/ytel/list-all-dnc-coming-soon", json_body={}))
		pp("Ytel delete-dnc (coming soon)", await call(client, "POST", "/api/v1/ytel/delete-dnc-coming-soon", json_body={}))
		pp("Ytel search-by-phone (coming soon)", await call(client, "POST", "/api/v1/ytel/search-by-phone-coming-soon", json_body={}))

		# Convoso (DNC and Leads tokens may differ)
		c_token_dnc = env("CONVOSO_AUTH_TOKEN") or env("CONVOSO_TOKEN_DNC")
		c_token_leads = env("CONVOSO_TOKEN_LEADS") or c_token_dnc
		c_query_dnc = f"?auth_token={c_token_dnc}" if c_token_dnc else ""
		c_query_leads = f"?auth_token={c_token_leads}" if c_token_leads else ""
		pp("Convoso add-dnc", await call(client, "POST", f"/api/v1/convoso/add-dnc{c_query_dnc}", json_body={"phone_number": PHONE_NUMBER, "phone_code": PHONE_CODE}))
		pp("Convoso search-dnc", await call(client, "POST", f"/api/v1/convoso/search-dnc{c_query_dnc}", json_body={"phone_number": PHONE_NUMBER, "phone_code": PHONE_CODE, "offset": 0, "limit": 10}))
		pp("Convoso delete-dnc", await call(client, "POST", f"/api/v1/convoso/delete-dnc{c_query_dnc}", json_body={"phone_number": PHONE_NUMBER, "phone_code": PHONE_CODE, "campaign_id": env("CONVOSO_CAMPAIGN_ID", "0")}))
		pp("Convoso upload-dnc-list (coming soon)", await call(client, "POST", "/api/v1/convoso/upload-dnc-list-coming-soon", json_body={}))
		pp("Convoso search-by-phone", await call(client, "POST", f"/api/v1/convoso/search-by-phone{c_query_leads}", json_body={"phone_number": PHONE_NUMBER}))

		# RingCentral
		rc_assertion = env("RINGCENTRAL_JWT_ASSERTION") or env("RINGCENTRAL_JWT")
		rc_basic_b64 = env("RINGCENTRAL_BASIC_B64")
		rc_token: Optional[str] = env("RINGCENTRAL_BEARER_TOKEN")
		if not rc_token and rc_assertion:
			pp("RingCentral auth", await call(client, "POST", f"/api/v1/ringcentral/auth?assertion={rc_assertion}" + (f"&client_basic_b64={rc_basic_b64}" if rc_basic_b64 else "")))
		rc_token = env("RINGCENTRAL_BEARER_TOKEN")
		rc_q = f"?bearer_token={rc_token}" if rc_token else ""
		pp("RingCentral add-dnc", await call(client, "POST", f"/api/v1/ringcentral/add-dnc{rc_q}", json_body={"phone_number": PHONE_NUMBER, "phone_code": PHONE_CODE}))
		pp("RingCentral list-all-dnc", await call(client, "POST", f"/api/v1/ringcentral/list-all-dnc{rc_q}", json_body={"page": 1, "per_page": 100, "status": env("RINGCENTRAL_DNC_STATUS", "Blocked")}))
		rc_resource_id = env("RINGCENTRAL_RESOURCE_ID")
		if rc_resource_id:
			pp("RingCentral delete-dnc", await call(client, "POST", f"/api/v1/ringcentral/delete-dnc{rc_q}", json_body={"resource_id": rc_resource_id}))
		else:
			pp("RingCentral delete-dnc (skipped: set RINGCENTRAL_RESOURCE_ID to test)", {"skipped": True})
		pp("RingCentral search-dnc (coming soon)", await call(client, "POST", "/api/v1/ringcentral/search-dnc-coming-soon", json_body={}))
		pp("RingCentral upload-dnc-list (coming soon)", await call(client, "POST", "/api/v1/ringcentral/upload-dnc-list-coming-soon", json_body={}))

		# Genesys
		g_token: Optional[str] = env("GENESYS_BEARER_TOKEN")
		g_client_id = env("GENESYS_CLIENT_ID")
		g_client_secret = env("GENESYS_CLIENT_SECRET")
		if not g_token and g_client_id and g_client_secret:
			pp("Genesys auth", await call(client, "POST", f"/api/v1/genesys/auth?client_id={g_client_id}&client_secret={g_client_secret}"))
		g_token = env("GENESYS_BEARER_TOKEN")
		g_q = f"?bearer_token={g_token}" if g_token else (f"?client_id={g_client_id}&client_secret={g_client_secret}" if g_client_id and g_client_secret else "")
		pp("Genesys list-all-dnc", await call(client, "POST", f"/api/v1/genesys/list-all-dnc{g_q}", json_body={"page": 1, "per_page": 50}))
		pp("Genesys add-dnc (coming soon)", await call(client, "POST", "/api/v1/genesys/add-dnc-coming-soon", json_body={}))
		pp("Genesys search-dnc (coming soon)", await call(client, "POST", "/api/v1/genesys/search-dnc-coming-soon", json_body={}))
		pp("Genesys delete-dnc (coming soon)", await call(client, "POST", "/api/v1/genesys/delete-dnc-coming-soon", json_body={}))
		pp("Genesys upload-dnc-list (coming soon)", await call(client, "POST", "/api/v1/genesys/upload-dnc-list-coming-soon", json_body={}))

		# Logics: use static Basic auth and optional cookie
		logics_b64 = env("LOGICS_BASIC_AUTH_B64")
		logics_cookie = env("LOGICS_COOKIE")
		l_q = f"?basic_auth_b64={logics_b64}" if logics_b64 else ""
		if logics_cookie:
			l_q += ("&" if l_q else "?") + f"cookie={logics_cookie}"
		search_resp = await call(client, "POST", f"/api/v1/logics/search-by-phone{l_q}", json_body={"phone_number": PHONE_NUMBER})
		pp("Logics search-by-phone", search_resp)
		case_id: Optional[int] = None
		try:
			data = search_resp.get("json") or {}
			if isinstance(data, dict):
				# Try nested shape: data.Data is a list of cases
				inner = data.get("data") or {}
				if isinstance(inner, dict):
					arr = inner.get("Data")
					if isinstance(arr, list) and len(arr) > 0 and isinstance(arr[0], dict):
						case_id = arr[0].get("CaseID")
				# Fallbacks
				case_id = case_id or data.get("CaseID") or data.get("caseId")
		except Exception:
			pass
		if case_id:
			status_id = int(env("LOGICS_UPDATE_STATUS_ID", "57"))
			pp("Logics update-case", await call(client, "POST", f"/api/v1/logics/update-case{l_q}", json_body={"case_id": case_id, "status_id": status_id}))
		else:
			pp("Logics update-case (skipped: no CaseID from search)", {"skipped": True})


if __name__ == "__main__":
	asyncio.run(run())
