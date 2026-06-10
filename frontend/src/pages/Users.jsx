import React, { useState, useEffect } from 'react'
import { Plus, Edit2, Trash2, ShieldCheck, User as UserIcon, X } from 'lucide-react'
import toast from 'react-hot-toast'
import api from '../utils/api'
import { PRODUCTS } from '../productRegistry'

// Permission groups — displayed as sections in the modal
const PERM_GROUPS = [
  {
    label: 'Data Entry',
    perms: [
      { key: 'upload',        label: 'Upload Files',               desc: 'Upload bank statements and dumps' },
      { key: 'clear_data',    label: 'Clear / Delete Data',        desc: 'Clear uploaded data and delete transactions' },
    ]
  },
  {
    label: 'Reconciliation',
    perms: [
      { key: 'run_recon',     label: 'Run Recon',                  desc: 'Run auto-match, NEFT D+1, interbank match' },
      { key: 'manual_match',  label: 'Manual Match',               desc: 'Manually pair bank ↔ internal transactions' },
      { key: 'src_assign',    label: 'Assign SRC / Adhoc Tag',     desc: 'Assign special reason codes and tag adhoc settlements' },
    ]
  },
  {
    label: 'Override & Admin',
    perms: [
      { key: 'override',      label: '⚠ Override / Unmatch',       desc: 'Break matches, bulk override, override status (requires remark)' },
      { key: 'approver',      label: '✓ Approver (Checker)',       desc: 'Maker-checker: can approve/reject other users\' queued manual actions. A maker can never approve their own request.' },
      { key: 'logic_builder', label: 'Logic Builder',              desc: 'Create and manage matching rules' },
    ]
  },
  {
    label: 'Reporting',
    perms: [
      { key: 'reports',       label: 'Reports',                    desc: 'View and export all reports' },
    ]
  },
]

// Flat list for backward compat
const PERMS = PERM_GROUPS.flatMap(g => g.perms.map(p => p.key))
const PERM_LABELS = Object.fromEntries(PERM_GROUPS.flatMap(g => g.perms.map(p => [p.key, p.label])))

const DEFAULT_PERMS = { upload: true, run_recon: true, src_assign: true, reports: true, logic_builder: false, override: false, manual_match: true, clear_data: false, approver: false }

export default function Users() {
  const [users, setUsers] = useState([])
  const [modal, setModal] = useState(null) // null | 'create' | user_obj
  const [form, setForm] = useState({ username: '', full_name: '', email: '', password: '', role: 'user', permissions: DEFAULT_PERMS, allowed_products: [] })

  const load = async () => {
    try { const { data } = await api.get('/auth/users'); setUsers(data) } catch {}
  }
  useEffect(() => { load() }, [])

  const openCreate = () => {
    setForm({ username: '', full_name: '', email: '', password: '', role: 'user', permissions: DEFAULT_PERMS, allowed_products: [] })
    setModal('create')
  }

  const openEdit = (user) => {
    setForm({ username: user.username, full_name: user.full_name || '', email: user.email || '', password: '', role: user.role, permissions: user.permissions || {}, allowed_products: user.allowed_products || [] })
    setModal(user)
  }

  const handleSave = async () => {
    try {
      if (modal === 'create') {
        await api.post('/auth/users', form)
        toast.success('User created')
      } else {
        const update = { full_name: form.full_name, email: form.email, permissions: form.permissions, allowed_products: form.allowed_products }
        if (form.password) update.password = form.password
        await api.put(`/auth/users/${modal.id}`, update)
        toast.success('Updated')
      }
      setModal(null); load()
    } catch (err) { toast.error(err.response?.data?.detail || 'Error') }
  }

  const toggleProduct = (id) => {
    setForm(f => ({
      ...f,
      allowed_products: f.allowed_products.includes(id)
        ? f.allowed_products.filter(p => p !== id)
        : [...f.allowed_products, id],
    }))
  }

  const handleDelete = async (user) => {
    if (!confirm(`Delete user ${user.username}?`)) return
    try { await api.delete(`/auth/users/${user.id}`); load(); toast.success('Deleted') } catch { toast.error('Failed') }
  }

  const togglePerm = (perm) => {
    setForm(f => ({ ...f, permissions: { ...f.permissions, [perm]: !f.permissions[perm] } }))
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-bold text-gray-800">User Management</h1>
        <button onClick={openCreate} className="btn-primary flex items-center gap-2"><Plus size={15} /> Add User</button>
      </div>
      <p className="text-sm text-gray-500 mb-5">Manage team access and permissions</p>

      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="table-th">User</th>
              <th className="table-th">Role</th>
              <th className="table-th">Permissions</th>
              <th className="table-th">Status</th>
              <th className="table-th">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map(user => (
              <tr key={user.id} className="hover:bg-gray-50 border-b border-gray-50">
                <td className="table-td">
                  <div className="flex items-center gap-2">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold ${user.role === 'admin' ? 'bg-primary' : 'bg-gray-400'}`}>
                      {(user.full_name || user.username)[0].toUpperCase()}
                    </div>
                    <div>
                      <div className="font-medium text-gray-800">{user.full_name || user.username}</div>
                      <div className="text-xs text-gray-400">@{user.username}</div>
                    </div>
                  </div>
                </td>
                <td className="table-td">
                  <span className={user.role === 'admin' ? 'badge-blue' : 'badge-gray'}>
                    {user.role === 'admin' ? <><ShieldCheck size={11} className="inline mr-1" />Admin</> : <><UserIcon size={11} className="inline mr-1" />User</>}
                  </span>
                </td>
                <td className="table-td">
                  <div className="flex flex-wrap gap-1">
                    {user.role === 'admin' ? (
                      <span className="badge-blue">All permissions</span>
                    ) : (
                      PERMS.filter(p => user.permissions?.[p]).map(p => (
                        <span key={p} className="badge-gray">{PERM_LABELS[p]}</span>
                      ))
                    )}
                  </div>
                </td>
                <td className="table-td">
                  <span className={user.is_active ? 'badge-green' : 'badge-red'}>{user.is_active ? 'Active' : 'Disabled'}</span>
                </td>
                <td className="table-td">
                  <div className="flex gap-2">
                    <button onClick={() => openEdit(user)} className="text-gray-400 hover:text-primary"><Edit2 size={14} /></button>
                    {user.username !== 'admin' && (
                      <button onClick={() => handleDelete(user)} className="text-gray-400 hover:text-red-500"><Trash2 size={14} /></button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal */}
      {modal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-800">{modal === 'create' ? 'Create User' : `Edit: ${modal.username}`}</h3>
              <button onClick={() => setModal(null)} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
            </div>
            <div className="space-y-3">
              {modal === 'create' && (
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Username</label>
                  <input className="input" value={form.username} onChange={e => setForm({...form, username: e.target.value})} />
                </div>
              )}
              <div>
                <label className="text-xs text-gray-500 block mb-1">Full Name</label>
                <input className="input" value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})} />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Email</label>
                <input className="input" type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">{modal === 'create' ? 'Password' : 'New Password (leave blank to keep)'}</label>
                <input className="input" type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} />
              </div>
              {modal === 'create' && (
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Role</label>
                  <select className="select" value={form.role} onChange={e => setForm({...form, role: e.target.value})}>
                    <option value="user">User</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
              )}
              {(modal === 'create' ? form.role === 'user' : modal.role === 'user') && (
                <div>
                  <label className="text-xs font-semibold text-gray-600 block mb-2">Permissions</label>
                  <div className="space-y-3 max-h-64 overflow-y-auto pr-1">
                    {PERM_GROUPS.map(group => (
                      <div key={group.label}>
                        <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5 border-b border-gray-100 pb-0.5">
                          {group.label}
                        </div>
                        <div className="space-y-1.5 pl-1">
                          {group.perms.map(({ key, label, desc }) => (
                            <label key={key} className="flex items-start gap-2 cursor-pointer">
                              <input type="checkbox" className="mt-0.5"
                                checked={!!form.permissions[key]} onChange={() => togglePerm(key)} />
                              <div>
                                <div className="text-sm text-gray-700">{label}</div>
                                <div className="text-xs text-gray-400">{desc}</div>
                              </div>
                            </label>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Product access — which reconciliations this user can work on */}
              {(modal === 'create' ? form.role === 'user' : modal.role === 'user') && (
                <div>
                  <label className="text-xs font-semibold text-gray-600 block mb-1">Product access</label>
                  <p className="text-[11px] text-gray-400 mb-2">
                    Tick the products this user reconciles. <strong>None ticked = access to all products.</strong>
                  </p>
                  <div className="grid grid-cols-2 gap-1.5">
                    {PRODUCTS.map(p => (
                      <label key={p.id} className="flex items-center gap-2 cursor-pointer text-sm text-gray-700">
                        <input type="checkbox"
                          checked={form.allowed_products.includes(p.id)}
                          onChange={() => toggleProduct(p.id)} />
                        <span>{p.icon} {p.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div className="flex gap-3 mt-5">
              <button onClick={() => setModal(null)} className="btn-ghost flex-1">Cancel</button>
              <button onClick={handleSave} className="btn-primary flex-1">
                {modal === 'create' ? 'Create User' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
