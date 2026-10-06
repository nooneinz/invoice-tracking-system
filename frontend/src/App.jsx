import { useEffect, useState, createContext, useContext } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { api, getToken, setToken, ROLE } from './api.js'
import { PublicHeader, Footer, Sidebar } from './layout.jsx'
import Login from './pages/Login.jsx'
import Home from './pages/Home.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Invoices from './pages/Invoices.jsx'
import InvoiceEditor from './pages/InvoiceEditor.jsx'
import InvoiceDetail from './pages/InvoiceDetail.jsx'
import Customers from './pages/Customers.jsx'
import Collections from './pages/Collections.jsx'
import Bank from './pages/Bank.jsx'
import Agents from './pages/Agents.jsx'
import Admin from './pages/Admin.jsx'
import Audit from './pages/Audit.jsx'

const Auth = createContext(null)
export const useAuth = () => useContext(Auth)

export default function App() {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)
  useEffect(() => {
    if (!getToken()) return setReady(true)
    api('/me').then(setUser).catch(() => setToken(null)).finally(() => setReady(true))
  }, [])
  const logout = () => { setToken(null); setUser(null) }
  if (!ready) return <p className="p-8">جارٍ التحميل…</p>
  if (!user) return (
    <Routes>
      <Route path="/login" element={<Login onLogin={setUser} />} />
      <Route path="*" element={<div className="min-h-screen flex flex-col"><PublicHeader /><Home /><Footer /></div>} />
    </Routes>
  )
  return (
    <Auth.Provider value={user}>
      <div className="min-h-screen lg:flex">
        <Sidebar user={user} roleLabel={ROLE[user.role]} onLogout={logout} />
        <div className="flex-1 min-w-0 flex flex-col">
          <main className="max-w-6xl w-full mx-auto px-4 lg:px-8 py-8 flex-1">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/invoices" element={<Invoices />} />
              <Route path="/invoices/new" element={<InvoiceEditor />} />
              <Route path="/invoices/:id/edit" element={<InvoiceEditor />} />
              <Route path="/invoices/:id" element={<InvoiceDetail />} />
              <Route path="/customers" element={<Customers />} />
              <Route path="/collections" element={<Collections />} />
              <Route path="/bank" element={<Bank />} />
              <Route path="/agents" element={<Agents />} />
              <Route path="/admin" element={<Admin />} />
              <Route path="/audit" element={<Audit />} />
              <Route path="/about" element={<div className="-mx-4 lg:-mx-8 -my-8"><Home authed /></div>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
          <footer className="text-center text-xs text-muted py-4 border-t border-line">تحصيل — توقيت مسقط (GMT+4) · الريال العماني</footer>
        </div>
      </div>
    </Auth.Provider>
  )
}
