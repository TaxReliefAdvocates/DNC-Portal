import React, { useState } from 'react'
import { useAppDispatch } from '@/lib/hooks'
import { setOrganization, setRole, setUser, setSuperAdmin } from '@/lib/features/auth/demoAuthSlice'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

interface Props { onLoggedIn?: () => void }

export const Login: React.FC<Props> = ({ onLoggedIn }) => {
  const dispatch = useAppDispatch()
  const [email, setEmail] = useState('admin@example.com')
  const [password, setPassword] = useState('admin')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const doLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/tenants/auth/password-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      })
      if (!resp.ok) throw new Error('Invalid email or password')
      const data = await resp.json()
      const userId = Number(data.user_id || 1)
      const orgId = Number(data.organization_id || 1)
      const role = String(data.role || 'member') as any
      dispatch(setUser(userId))
      dispatch(setOrganization(orgId))
      dispatch(setRole(role))
      onLoggedIn?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Login failed')
    } finally { setLoading(false) }
  }

  return (
    <div className="max-w-md mx-auto">
      <Card>
        <CardHeader>
          <CardTitle>Login</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={doLogin} className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700">Email</label>
              <input className="mt-1 w-full border rounded px-3 py-2" value={email} onChange={(e)=>setEmail(e.target.value)} placeholder="you@example.com" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Password</label>
              <input type="password" className="mt-1 w-full border rounded px-3 py-2" value={password} onChange={(e)=>setPassword(e.target.value)} placeholder="••••••••" />
            </div>
            {error && <div className="text-sm text-red-600">{error}</div>}
            <div className="flex items-center gap-2">
              <Button type="submit" disabled={loading}>{loading ? 'Signing in…' : 'Sign In'}</Button>
              <Button type="button" variant="outline" onClick={async ()=>{
                try {
                  const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/tenants/auth/login`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ username:'admin', password:'admin' }) })
                  if (resp.ok) {
                    dispatch(setSuperAdmin())
                    onLoggedIn?.()
                  } else {
                    setError('Dev login failed')
                  }
                } catch { setError('Dev login failed') }
              }}>Dev Login (admin/admin)</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}


