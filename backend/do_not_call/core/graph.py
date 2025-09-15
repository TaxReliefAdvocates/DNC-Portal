from __future__ import annotations

import httpx
from typing import Optional
from ..config import settings


class GraphClient:
    """Minimal Microsoft Graph client for App Role Assignments."""

    def __init__(self):
        self.tenant = settings.GRAPH_TENANT_ID or settings.ENTRA_TENANT_ID
        self.client_id = settings.GRAPH_CLIENT_ID
        self.client_secret = settings.GRAPH_CLIENT_SECRET
        self.scope = "https://graph.microsoft.com/.default"
        self.token: Optional[str] = None

    async def _acquire_token(self) -> str:
        if self.token:
            return self.token
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
            "scope": self.scope,
        }
        url = f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token"
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, data=data)
            r.raise_for_status()
            self.token = r.json()["access_token"]
            return self.token

    async def assign_app_role(self, user_object_id: str, app_id: str, app_role_id: str) -> dict:
        token = await self._acquire_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        # Get the service principal for the API app
        async with httpx.AsyncClient(timeout=30) as client:
            sp = await client.get(
                f"https://graph.microsoft.com/v1.0/servicePrincipals?$filter=appId eq '{app_id}'",
                headers=headers,
            )
            sp.raise_for_status()
            sp_json = sp.json()
            sp_id = sp_json.get("value", [{}])[0].get("id")
            body = {
                "principalId": user_object_id,
                "resourceId": sp_id,
                "appRoleId": app_role_id,
            }
            resp = await client.post(
                f"https://graph.microsoft.com/v1.0/users/{user_object_id}/appRoleAssignments",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    async def remove_app_role(self, assignment_id: str, user_object_id: str) -> None:
        token = await self._acquire_token()
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.delete(
                f"https://graph.microsoft.com/v1.0/users/{user_object_id}/appRoleAssignments/{assignment_id}",
                headers=headers,
            )
            r.raise_for_status()



