# Deploy DNC Portal to Render

## Prerequisites
1. **Azure PostgreSQL Database** - Make sure your database is accessible
2. **Render Account** - Sign up at render.com
3. **GitHub Repository** - Push your code to GitHub

## Deployment Steps

### 1. **Backend Deployment**
1. Go to Render Dashboard
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: `dnc-portal-backend`
   - **Environment**: `Python 3`
   - **Build Command**: 
     ```bash
     cd backend
     pip install poetry
     poetry install
     poetry run alembic upgrade head
     ```
   - **Start Command**: 
     ```bash
     cd backend
     poetry run uvicorn do_not_call.main:app --host 0.0.0.0 --port $PORT
     ```

### 2. **Environment Variables for Backend**
Add these in Render's Environment tab:
```
DATABASE_URL=postgresql+psycopg2://traadmin:TPSZen2025%40%21@dnc.postgres.database.azure.com:5432/postgres?sslmode=require
PGHOST=dnc.postgres.database.azure.com
PGUSER=traadmin
PGPORT=5432
PGDATABASE=postgres
PGPASSWORD=TPSZen2025@!
DEBUG=false
LOG_LEVEL=INFO
```

### 3. **Frontend Deployment**
1. Go to Render Dashboard
2. Click "New +" → "Static Site"
3. Connect your GitHub repository
4. Configure:
   - **Name**: `dnc-portal-frontend`
   - **Build Command**: 
     ```bash
     cd frontend
     npm install -g pnpm
     pnpm install
     pnpm build
     ```
   - **Publish Directory**: `frontend/dist`

### 4. **Environment Variables for Frontend**
Add these in Render's Environment tab:
```
VITE_API_BASE_URL=https://dnc-portal-backend.onrender.com
VITE_ENTRA_TENANT_ID=185fc38c-2c1b-4307-a164-24a4072e83e1
VITE_ENTRA_SPA_CLIENT_ID=a2a6c2c2-cb10-411e-a354-da61bfa4a3b2
VITE_ENTRA_SCOPE=api://a2a6c2c2-cb10-411e-a354-da61bfa4a3b2/access_as_user
```

## Database Issues

### **If you get "access token expired" error:**
Your Azure PostgreSQL is configured for Azure AD authentication. You need to:

1. **Enable password authentication** in Azure Portal:
   - Go to your PostgreSQL server
   - Settings → Server parameters
   - Find `azure.accepted_password_auth_method`
   - Set to `md5,scram-sha-256`

2. **Or use the correct password** for the `traadmin` user

### **If you get connection refused:**
1. Check firewall rules in Azure Portal
2. Make sure your IP is allowed
3. Verify the database server is running

## Testing

After deployment:
1. Backend should be available at: `https://dnc-portal-backend.onrender.com`
2. Frontend should be available at: `https://dnc-portal-frontend.onrender.com`
3. Test the API: `https://dnc-portal-backend.onrender.com/docs`

## Troubleshooting

- **Build fails**: Check the build logs in Render
- **Database connection fails**: Verify environment variables
- **Frontend can't reach backend**: Check CORS settings and API URL