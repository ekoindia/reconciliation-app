import React, { useState, useEffect, useCallback } from 'react'
import { Plus, Trash2, Edit3, CheckCircle, AlertTriangle, RefreshCw, X } from 'lucide-react'
import api from '../utils/api'
import toast from 'react-hot-toast'

// ── Formatters ─────────────────────────────────────────────────────────────────

function fmtINR(n) {
  if (n == null || isNaN(n) || n === 0) return '₹0.00'
  return `₹${Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function today() { return new Date().toISOString().split('T')[0] }
function monthStart() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-01`
}

// ── Settlement Tab ─────────────────────────────────────────────────────────────

function SettlementTab({ dateFrom, dateTo }) {
  const [data, setData]   = useState(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data: d } = await api.get('/qr/settlement-summary', {
        params: { ...(dateFrom && { date_from: dateFrom }), ...(dateTo && { date_to: dateTo }) }
      })
      setData(d)
    } catch { toast.error('Failed to load settlement') } finally { setLoading(false) }
  }, [dateFrom, dateTo])

  useEffect(() => { load() }, [load])

  if (loading) return <div className="text-center py-12 text-gray-400 text-sm">Loading…</div>
  if (!data || data.rows.length === 0) return (
    <div className="text-center py-12 text-gray-400">
      <div className="text-4xl mb-3">💰</div>
      <p className="text-sm font-medium">No settlement records</p>
      <p className="text-xs mt-1">Upload a Settlement Report from Upload Files → QR Collection</p>
    </div>
  )

  const g = data.grand
  const total_deductions = g.fees + g.fees_tax + g.early_settlement_fees + g.early_settlement_tax

  return (
    <div>
      {/* Grand totals */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        {[
          { label: 'Gross Amount',    value: fmtINR(g.gross_amount),   color: 'text-gray-800' },
          { label: 'Total Fees',       value: fmtINR(total_deductions), color: 'text-amber-600' },
          { label: 'Net Settlement',   value: fmtINR(g.net_settlement), color: 'text-green-700 font-bold' },
          { label: 'Settlement Batches', value: String(data.rows.length), color: 'text-gray-600' },
        ].map(({ label, value, color }) => (
          <div key={label} className="card p-4 text-center">
            <div className={`text-lg font-bold ${color}`}>{value}</div>
            <div className="text-xs text-gray-400 mt-0.5">{label}</div>
          </div>
        ))}
      </div>

      {/* Settlement table */}
      <div className="card overflow-hidden p-0">
        <div className="px-5 py-3 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-700">Settlement Batches</span>
          <span className="text-xs text-gray-400">{data.rows.length} records</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50 text-xs text-gray-400 uppercase tracking-wide">
                <th className="text-left px-4 py-2.5">Settlement ID</th>
                <th className="text-left px-4 py-2.5">Payment Date</th>
                <th className="text-right px-4 py-2.5">Gross Amount</th>
                <th className="text-right px-4 py-2.5 text-amber-500">Fees</th>
                <th className="text-right px-4 py-2.5 text-amber-500">Fees Tax</th>
                <th className="text-right px-4 py-2.5 text-amber-500">Early Sett.</th>
                <th className="text-right px-4 py-2.5 text-green-600">Net Settlement</th>
                <th className="text-center px-4 py-2.5">Formula</th>
                <th className="text-left px-4 py-2.5">Bank Ref</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map(r => (
                <tr key={r.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-2.5 text-xs font-mono text-gray-600">{r.settlement_id}</td>
                  <td className="px-4 py-2.5 text-xs text-gray-500">{r.payment_date}</td>
                  <td className="px-4 py-2.5 text-right font-medium tabular-nums">{fmtINR(r.gross_amount)}</td>
                  <td className="px-4 py-2.5 text-right text-amber-600 tabular-nums text-xs">
                    {fmtINR(r.fees)}
                    {r.fees_tax > 0 && <div className="text-gray-400">+{fmtINR(r.fees_tax)} tax</div>}
                  </td>
                  <td className="px-4 py-2.5 text-right text-amber-600 tabular-nums text-xs">
                    {r.early_settlement_fees > 0 ? fmtINR(r.early_settlement_fees) : '—'}
                    {r.early_settlement_tax > 0 && <div className="text-gray-400">+{fmtINR(r.early_settlement_tax)}</div>}
                  </td>
                  <td className="px-4 py-2.5 text-right font-bold text-green-700 tabular-nums">{fmtINR(r.net_settlement)}</td>
                  <td className="px-4 py-2.5 text-center">
                    {r.formula_ok
                      ? <span className="text-green-600 text-xs font-medium flex items-center justify-center gap-1"><CheckCircle size={12}/>OK</span>
                      : <span className="text-red-500 text-xs font-medium flex items-center justify-center gap-1"><AlertTriangle size={12}/>Diff {fmtINR(r.diff)}</span>
                    }
                  </td>
                  <td className="px-4 py-2.5 text-xs font-mono text-gray-400">{r.bank_ref_number}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="mt-4 bg-blue-50 border border-blue-100 rounded-xl p-4 text-xs text-blue-700">
        <span className="font-semibold">Formula: </span>
        Net Settlement = Gross Amount − Fees − Fees Tax − Early Settlement Fees − Early Settlement Tax
      </div>
    </div>
  )
}

// ── Chargeback Tab ─────────────────────────────────────────────────────────────

const STATUS_COLORS = {
  pending:  'bg-amber-100 text-amber-700',
  settled:  'bg-green-100 text-green-700',
  defended: 'bg-blue-100 text-blue-700',
}

function ChargebackForm({ initial, onSave, onCancel }) {
  const empty = { case_date: today(), adj_type: 'Complaint Raise', txn_date: today(),
                  upi_txn_id: '', rrn: '', adj_amount: '', tat_date: '', status: 'pending', notes: '' }
  const [form, setForm] = useState(initial || empty)
  const [saving, setSaving] = useState(false)
  const upd = patch => setForm(f => ({ ...f, ...patch }))

  const handleSave = async () => {
    if (!form.rrn || !form.adj_amount) return toast.error('RRN and Amount are required')
    setSaving(true)
    try {
      if (initial?.id) {
        await api.put(`/qr/chargebacks/${initial.id}`, { ...form, adj_amount: parseFloat(form.adj_amount) })
        toast.success('Chargeback updated')
      } else {
        await api.post('/qr/chargebacks', { ...form, adj_amount: parseFloat(form.adj_amount) })
        toast.success('Chargeback added')
      }
      onSave()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Save failed')
    } finally { setSaving(false) }
  }

  return (
    <div className="card mb-5 border border-indigo-100">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-800 text-sm">
          {initial?.id ? 'Edit Chargeback' : 'Add Chargeback (from email)'}
        </h3>
        <button onClick={onCancel} className="text-gray-400 hover:text-gray-600"><X size={16}/></button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div>
          <label className="text-xs text-gray-500 block mb-1">Case Received Date *</label>
          <input type="date" className="input" value={form.case_date} onChange={e => upd({ case_date: e.target.value })} />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">Adj Type</label>
          <input className="input" value={form.adj_type} onChange={e => upd({ adj_type: e.target.value })} placeholder="Complaint Raise" />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">Transaction Date *</label>
          <input type="date" className="input" value={form.txn_date} onChange={e => upd({ txn_date: e.target.value })} />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">TAT Deadline</label>
          <input type="date" className="input" value={form.tat_date} onChange={e => upd({ tat_date: e.target.value })} />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">RRN * <span className="text-gray-400">(from email)</span></label>
          <input className="input font-mono" value={form.rrn} onChange={e => upd({ rrn: e.target.value })} placeholder="999900001234" />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">UPI Txn ID</label>
          <input className="input font-mono text-xs" value={form.upi_txn_id} onChange={e => upd({ upi_txn_id: e.target.value })} placeholder="PTMb71f420948a342429..." />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">Amount (₹) *</label>
          <input type="number" className="input" value={form.adj_amount} onChange={e => upd({ adj_amount: e.target.value })} placeholder="39500" />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">Status</label>
          <select className="select" value={form.status} onChange={e => upd({ status: e.target.value })}>
            <option value="pending">Pending</option>
            <option value="settled">Settled</option>
            <option value="defended">Defended</option>
          </select>
        </div>
        <div className="col-span-2 md:col-span-4">
          <label className="text-xs text-gray-500 block mb-1">Notes</label>
          <input className="input" value={form.notes} onChange={e => upd({ notes: e.target.value })} placeholder="Additional context..." />
        </div>
      </div>
      <div className="flex gap-3">
        <button onClick={onCancel} className="btn-ghost">Cancel</button>
        <button onClick={handleSave} disabled={saving} className="btn-primary">
          {saving ? 'Saving…' : initial?.id ? 'Update' : 'Add Chargeback'}
        </button>
      </div>
    </div>
  )
}

function ChargebackTab({ dateFrom, dateTo }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing]   = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data: d } = await api.get('/qr/chargebacks', {
        params: { ...(dateFrom && { date_from: dateFrom }), ...(dateTo && { date_to: dateTo }) }
      })
      setData(d)
    } catch { toast.error('Failed to load chargebacks') } finally { setLoading(false) }
  }, [dateFrom, dateTo])

  useEffect(() => { load() }, [load])

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this chargeback entry?')) return
    try { await api.delete(`/qr/chargebacks/${id}`); toast.success('Deleted'); load() }
    catch { toast.error('Delete failed') }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          {data && (
            <div className="flex gap-4 text-sm">
              <span className="text-amber-600 font-semibold">Pending: {fmtINR(data.total_pending)}</span>
              <span className="text-green-600 font-semibold">Settled/Defended: {fmtINR(data.total_settled)}</span>
              <span className="text-gray-500">Total: {data.count} entries</span>
            </div>
          )}
        </div>
        <button onClick={() => { setShowForm(true); setEditing(null) }}
          className="btn-primary flex items-center gap-1.5 text-sm" style={{ background: '#dc2626' }}>
          <Plus size={14} /> Add from Email
        </button>
      </div>

      {(showForm && !editing) && (
        <ChargebackForm onSave={() => { setShowForm(false); load() }} onCancel={() => setShowForm(false)} />
      )}
      {editing && (
        <ChargebackForm initial={editing} onSave={() => { setEditing(null); load() }} onCancel={() => setEditing(null)} />
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-400 text-sm">Loading…</div>
      ) : !data || data.rows.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <div className="text-4xl mb-3">🔴</div>
          <p className="text-sm font-medium">No chargeback entries yet</p>
          <p className="text-xs mt-1">Click "Add from Email" to enter details from a Paypoint chargeback email</p>
        </div>
      ) : (
        <div className="card overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50 text-xs text-gray-400 uppercase tracking-wide">
                  <th className="text-left px-4 py-2.5">Case Date</th>
                  <th className="text-left px-4 py-2.5">RRN</th>
                  <th className="text-right px-4 py-2.5">Amount</th>
                  <th className="text-left px-4 py-2.5">Adj Type</th>
                  <th className="text-left px-4 py-2.5">Txn Date</th>
                  <th className="text-left px-4 py-2.5">TAT</th>
                  <th className="text-center px-4 py-2.5">Bank Txn</th>
                  <th className="text-left px-4 py-2.5">Bank TID</th>
                  <th className="text-center px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map(r => (
                  <tr key={r.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-2.5 text-xs font-mono">{r.case_date}</td>
                    <td className="px-4 py-2.5 text-xs font-mono text-gray-600">{r.rrn}</td>
                    <td className="px-4 py-2.5 text-right font-semibold text-red-600 tabular-nums">{fmtINR(r.adj_amount)}</td>
                    <td className="px-4 py-2.5 text-xs text-gray-500">{r.adj_type}</td>
                    <td className="px-4 py-2.5 text-xs font-mono">{r.txn_date}</td>
                    <td className="px-4 py-2.5 text-xs font-mono">
                      <span className={r.tat_date && r.tat_date < today() && r.status === 'pending' ? 'text-red-500 font-semibold' : ''}>
                        {r.tat_date || '—'}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      {r.bank_txn_found
                        ? <span className="text-green-600 text-xs font-medium">✓ Found</span>
                        : <span className="text-red-400 text-xs">✗ Missing</span>
                      }
                    </td>
                    <td className="px-4 py-2.5 text-xs font-mono text-gray-500">{r.bank_eko_tid || '—'}</td>
                    <td className="px-4 py-2.5 text-center">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[r.status] || 'bg-gray-100 text-gray-600'}`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <button onClick={() => { setEditing(r); setShowForm(false) }}
                          className="text-gray-400 hover:text-primary"><Edit3 size={13}/></button>
                        <button onClick={() => handleDelete(r.id)}
                          className="text-gray-400 hover:text-red-500"><Trash2 size={13}/></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <div className="mt-4 bg-red-50 border border-red-100 rounded-xl p-4 text-xs text-red-700">
        <span className="font-semibold">Process: </span>
        Enter details from Paypoint chargeback email. The RRN cross-references the original bank transaction.
        Update status to "Settled" when the amount is withdrawn from CSP, or "Defended" when successfully disputed.
        Watch TAT deadlines — highlighted in red when past due.
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────

const TABS = [
  { key: 'settlement',  label: '💰 Settlement',  desc: 'Batch settlement verification' },
  { key: 'chargebacks', label: '🔴 Chargebacks', desc: 'Chargeback & dispute management' },
]

export default function QRSettlement({ embedded = false }) {
  const [tab, setTab]         = useState('settlement')
  const [dateFrom, setDateFrom] = useState(monthStart())
  const [dateTo, setDateTo]   = useState(today())
  const [clearing, setClearing] = useState(false)

  const clearAll = async () => {
    if (!window.confirm('Clear ALL QR settlement data? This cannot be undone.')) return
    setClearing(true)
    try {
      await api.delete('/qr/clear?report_type=all')
      toast.success('QR settlement data cleared')
    } catch { toast.error('Clear failed') } finally { setClearing(false) }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div>
          {!embedded && <h1 className="text-xl font-bold text-gray-800">QR Settlement Recon</h1>}
          <p className="text-sm text-gray-400">Settlement verification · Chargeback management</p>
        </div>
        <button onClick={clearAll} disabled={clearing}
          className="btn-ghost flex items-center gap-1.5 text-sm text-red-500 hover:border-red-200">
          <Trash2 size={13} /> Clear Data
        </button>
      </div>

      {/* Date filter */}
      <div className="card mb-5">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="text-xs text-gray-400 block mb-1">From</label>
            <input type="date" className="input" value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">To</label>
            <input type="date" className="input" value={dateTo} onChange={e => setDateTo(e.target.value)} />
          </div>
          <div className="flex gap-2 ml-auto">
            {[
              { label: 'This Month', fn: () => { setDateFrom(monthStart()); setDateTo(today()) } },
              { label: 'All Dates',  fn: () => { setDateFrom(''); setDateTo('') } },
            ].map(({ label, fn }) => (
              <button key={label} onClick={fn}
                className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50">
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 mb-5 border-b border-gray-200">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors
              ${tab === t.key ? 'border-primary text-primary' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'settlement'  && <SettlementTab  dateFrom={dateFrom} dateTo={dateTo} />}
      {tab === 'chargebacks' && <ChargebackTab  dateFrom={dateFrom} dateTo={dateTo} />}
    </div>
  )
}
