import React, { useEffect, useState } from 'react'
import { Button } from '../ui/button'

export const Login: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const scope = import.meta.env.VITE_ENTRA_SCOPE

  useEffect(() => {
    if (location.pathname !== '/login') {
      window.history.replaceState({}, '', '/login')
    }
  }, [])

  const signIn = async () => {
    setError(null)
    setLoading(true)
    try {
      const acquire = (window as any).__msalAcquireToken as (scopes: string[]) => Promise<string>
      if (!acquire) throw new Error('Auth not initialized')
      await acquire([scope])
      // On success, return to root
      if (location.pathname !== '/') {
        window.history.replaceState({}, '', '/')
      }
    } catch (e:any) {
      setError(e?.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-md mx-auto mt-16 p-6 bg-white border rounded">
      <h2 className="text-xl font-semibold mb-3">Sign in</h2>
      <p className="text-sm text-gray-600 mb-4">Use your Microsoft account to sign in.</p>
      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      <Button onClick={signIn} disabled={loading}>
        {loading ? 'Signing in…' : 'Sign in with Microsoft'}
      </Button>
    </div>
  )
}


