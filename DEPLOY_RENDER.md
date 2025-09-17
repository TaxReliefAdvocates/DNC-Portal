## Deploy to Render

This repo includes a Render Blueprint (`render.yaml`) to deploy the backend (FastAPI) and frontend (Vite/React).

### 1) Create services from the Blueprint
- In Render: New → Blueprint → select this repo/branch.
- It will create:
  - `dnc-backend` (Web Service, Python 3.12)
  - `dnc-frontend` (Static Site)

### 2) Set environment variables

Backend `dnc-backend`:
- `DATABASE_URL` (required): `postgresql://<user>:<password>@<host>:5432/<db>?sslmode=require`
- `ALLOWED_ORIGIN_REGEX` (optional): `https://.*\.onrender\.com|http://localhost:5173`
- `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD`: `1`
- `RELOAD`: `false`

Frontend `dnc-frontend`:
- `VITE_API_BASE_URL`: backend URL after first deploy (e.g. `https://dnc-backend.onrender.com`)
- `VITE_ENTRA_TENANT_ID`: your tenant ID
- `VITE_ENTRA_SPA_CLIENT_ID`: SPA client ID
- `VITE_ENTRA_SCOPE`: API scope (e.g. `api://<API_APP_ID>/.default`)

Re-deploy the frontend after setting `VITE_API_BASE_URL`.

### 3) Notes
- Backend listens on `$PORT` (Render) and runs `uvicorn do_not_call.main:app`.
- CORS is controlled by `ALLOWED_ORIGIN_REGEX`; narrow to your exact frontend hostname when known.
- Use the Logs tab on each service if there are startup issues.

