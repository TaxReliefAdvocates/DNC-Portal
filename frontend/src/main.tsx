import React from 'react'
import ReactDOM from 'react-dom/client'
import { PublicClientApplication, SilentRequest } from '@azure/msal-browser'
import { MsalProvider } from '@azure/msal-react'
import App from './App.tsx'
import './index.css'

const msal = new PublicClientApplication({
  auth: {
    clientId: import.meta.env.VITE_ENTRA_SPA_CLIENT_ID || '',
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_ENTRA_TENANT_ID}`,
    redirectUri: window.location.origin,
    postLogoutRedirectUri: window.location.origin,
  },
  cache: { cacheLocation: 'localStorage' }
})

// Expose a minimal token getter for api.ts to use
;(window as any).__msalAcquireToken = async (scopes: string[]) => {
  try {
    const accounts = msal.getAllAccounts()
    if (accounts.length === 0) {
      await msal.loginPopup({ scopes })
    }
    const req: SilentRequest = { account: msal.getAllAccounts()[0], scopes }
    const res = await msal.acquireTokenSilent(req)
    return res.accessToken
  } catch {
    const res = await msal.loginPopup({ scopes })
    return res.accessToken
  }
}

;(window as any).__msalLogout = async () => {
  try {
    await msal.logoutPopup()
  } catch {
    await msal.logoutRedirect()
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <MsalProvider instance={msal}>
      <App />
    </MsalProvider>
  </React.StrictMode>,
)





