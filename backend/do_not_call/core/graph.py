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
        # Client credentials flow against v2.0 endpoint
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

    def _normalize_app_id(self, app_id: str) -> str:
        # Accept either GUID or api://GUID; Graph needs the GUID
        if app_id and app_id.startswith("api://"):
            return app_id.split("api://", 1)[1]
        return app_id

    async def _get_api_service_principal_id(self, app_id: str) -> str:
        token = await self._acquire_token()
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                f"https://graph.microsoft.com/v1.0/servicePrincipals?$filter=appId eq '{app_id}'",
                headers=headers,
            )
            r.raise_for_status()
            val = r.json().get("value", [])
            if not val:
                raise RuntimeError("API service principal not found for given appId")
            return val[0]["id"]

    async def list_app_roles(self, app_id: str) -> dict:
        token = await self._acquire_token()
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                f"https://graph.microsoft.com/v1.0/applications?$filter=appId eq '{self._normalize_app_id(app_id)}'",
                headers=headers,
            )
            r.raise_for_status()
            app = (r.json().get("value") or [{}])[0]
            return {"id": app.get("id"), "appId": app.get("appId"), "appRoles": app.get("appRoles", [])}

    async def update_app_roles(self, application_object_id: str, app_roles: list[dict]) -> dict:
        token = await self._acquire_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.patch(
                f"https://graph.microsoft.com/v1.0/applications/{application_object_id}",
                headers=headers,
                json={"appRoles": app_roles},
            )
            r.raise_for_status()
            return r.json() if r.text else {"updated": True}

    async def list_user_role_assignments(self, user_object_id: str, app_id: str) -> dict:
        token = await self._acquire_token()
        headers = {"Authorization": f"Bearer {token}"}
        sp_id = await self._get_api_service_principal_id(self._normalize_app_id(app_id))
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                f"https://graph.microsoft.com/v1.0/users/{user_object_id}/appRoleAssignments?$filter=resourceId eq '{sp_id}'",
                headers=headers,
            )
            r.raise_for_status()
            return r.json()

    async def list_app_role_assignments(self, app_id: str) -> dict:
        """List all app role assignments for the API application's service principal."""
        token = await self._acquire_token()
        headers = {"Authorization": f"Bearer {token}"}
        sp_id = await self._get_api_service_principal_id(self._normalize_app_id(app_id))
        url = f"https://graph.microsoft.com/v1.0/servicePrincipals/{sp_id}/appRoleAssignedTo"
        async with httpx.AsyncClient(timeout=30) as client:
            all_values = []
            next_url = url
            while next_url:
                r = await client.get(next_url, headers=headers)
                r.raise_for_status()
                data = r.json()
                all_values.extend(data.get("value", []))
                next_url = data.get("@odata.nextLink")
            return {"value": all_values}

    async def get_user(self, user_object_id: str) -> dict:
        token = await self._acquire_token()
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"https://graph.microsoft.com/v1.0/users/{user_object_id}", headers=headers)
            r.raise_for_status()
            return r.json()

    async def assign_app_role(self, user_object_id: str, app_id: str, app_role_id: str) -> dict:
        token = await self._acquire_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        # Get the service principal for the API app
        async with httpx.AsyncClient(timeout=30) as client:
            sp = await client.get(
                f"https://graph.microsoft.com/v1.0/servicePrincipals?$filter=appId eq '{self._normalize_app_id(app_id)}'",
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



