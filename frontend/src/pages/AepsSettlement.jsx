import React, { useState, useEffect, useCallback } from 'react'
import { AlertTriangle, CheckCircle, RefreshCw, ExternalLink, Download, Trash2 } from 'lucide-react'
import api from '../utils/api'
import toast from 'react-hot-toast'

// ── Formatters ─────────────────────────────────────────────────────────────────

function fmtINR(n) {
  if (n == null || isNaN(n) || n === 0) return '₹0.00'
  return `₹${Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function today() { return new Date().toISOString().split('T')[0] }
function monthStart() {
  const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-01`
}

// ── Settlement Tab ─────────────────────────────────────────────────────────────

function SettlementTab({ dateFrom, dateTo }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (dateFrom) params.date_from = dateFrom
      if (dateTo)   params.date_to   = dateTo
      const { data: d } = await api.get('/aeps/settlement-summary', { params })
      setData(d)
    } catch { toast.error('Failed to load settlement data') }
    finally { setLoading(false) }
  }, [dateFrom, dateTo])

  useEffect(() => { load() }, [load])

  if (loading) return <div className="text-center py-12 text-gray-400 text-sm">Loading…</div>
  if (!data || data.rows.length === 0) return (
    <div className="text-center py-12 text-gray-400">
      <div className="text-4xl mb-3">📊</div>
      <p className="text-sm font-medium">No T Plus settlement records</p>
      <p className="text-xs mt-1">Upload a T Plus report from the Upload Files page</p>
    </div>
  )

  const g = data.grand

  return (
    <div>
      {/* Grand total strip */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-5">
        {[
          { label: 'Gross Txn Volume',   value: fmtINR(g.transaction_amount), color: 'text-gray-800' },
          { label: '3-Way Anomaly Ded.', value: fmtINR(g.anomaly_amount),     color: 'text-amber-600' },
          { label: '2FA Charges',         value: fmtINR(g.twafa_total),        color: 'text-amber-600' },
          { label: 'Chargeback Ded.',     value: fmtINR(g.cd_amount),          color: 'text-red-500'   },
          { label: 'Net Settlement',      value: fmtINR(g.settlement_amount),  color: 'text-green-700 font-bold' },
        ].map(({ label, value, color }) => (
          <div key={label} className="card p-4 text-center">
            <div className={`text-lg font-bold ${color}`}>{value}</div>
            <div className="text-xs text-gray-400 mt-0.5">{label}</div>
          </div>
        ))}
      </div>

      {/* Per-settlement table */}
      <div className="card overflow-hidden p-0">
        <div className="px-5 py-3 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-700">Settlement Records</span>
          <span className="text-xs text-gray-400">{data.rows.length} batch{data.rows.length !== 1 ? 'es' : ''}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50 text-xs text-gray-400 uppercase tracking-wide">
                <th className="text-left px-4 py-2.5">Date</th>
                <th className="text-right px-4 py-2.5">Txn Volume</th>
                <th className="text-right px-4 py-2.5 text-amber-500">Anomaly Ded.</th>
                <th className="text-right px-4 py-2.5 text-amber-500">2FA Ded.</th>
                <th className="text-right px-4 py-2.5 text-red-400">CB Ded.</th>
                <th className="text-right px-4 py-2.5 text-green-600">Net Settlement</th>
                <th className="text-center px-4 py-2.5">Formula</th>
                <th className="text-center px-4 py-2.5">Anomaly Cross-check</th>
                <th className="text-left px-4 py-2.5">Reference</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map(r => (
                <tr key={r.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-mono text-xs">{r.created_date}</td>
                  <td className="px-4 py-3 text-right tabular-nums font-medium">{fmtINR(r.transaction_amount)}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-amber-600">{fmtINR(r.anomaly_amount)}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-amber-600">
                    {fmtINR(r.twafa_total)}
                    <div className="text-xs text-gray-400">{r.twafa_count} × ₹{r.twafa_per_txn}</div>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-red-500">{fmtINR(r.cd_amount)}</td>
                  <td className="px-4 py-3 text-right tabular-nums font-bold text-green-700">{fmtINR(r.settlement_amount)}</td>
                  <td className="px-4 py-3 text-center">
                    {r.formula_ok
                      ? <span className="text-green-600 flex items-center justify-center gap-1 text-xs font-medium"><CheckCircle size={13}/>OK</span>
                      : <span className="text-red-500 flex items-center justify-center gap-1 text-xs font-medium">
                          <AlertTriangle size={13}/>Diff {fmtINR(r.diff)}
                        </span>
                    }
                  </td>
                  <td className="px-4 py-3 text-center">
                    {r.anomaly_uploaded > 0
                      ? r.anomaly_cross_ok
                        ? <span className="text-green-600 text-xs font-medium flex items-center justify-center gap-1"><CheckCircle size={13}/>{fmtINR(r.anomaly_uploaded)}</span>
                        : <span className="text-amber-600 text-xs font-medium flex items-center justify-center gap-1">
                            <AlertTriangle size={13}/>Uploaded {fmtINR(r.anomaly_uploaded)} / Expected {fmtINR(r.anomaly_amount)}
                          </span>
                      : <span className="text-gray-400 text-xs">Not uploaded</span>
                    }
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400 font-mono">
                    <div>{r.reference_number}</div>
                    <div className="text-gray-300">{r.cms_number}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Formula explanation */}
      <div className="mt-4 bg-blue-50 border border-blue-100 rounded-xl p-4 text-xs text-blue-700">
        <span className="font-semibold">Settlement Formula: </span>
        Net Settlement = Gross Txn Volume − 3-Way Anomaly − 2FA Charges (incl. GST) − Chargeback Deductions
      </div>
    </div>
  )
}

// ── Anomaly Tab ────────────────────────────────────────────────────────────────

function AnomalyTab({ dateFrom, dateTo }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (dateFrom) params.date_from = dateFrom
      if (dateTo)   params.date_to   = dateTo
      const { data: d } = await api.get('/aeps/anomaly-list', { params })
      setData(d)
    } catch { toast.error('Failed to load anomaly data') }
    finally { setLoading(false) }
  }, [dateFrom, dateTo])

  useEffect(() => { load() }, [load])

  if (loading) return <div className="text-center py-12 text-gray-400 text-sm">Loading…</div>
  if (!data || data.rows.length === 0) return (
    <div className="text-center py-12 text-gray-400">
      <div className="text-4xl mb-3">⚠️</div>
      <p className="text-sm font-medium">No Anomaly entries</p>
      <p className="text-xs mt-1">Upload an Anomaly RRN report from the Upload Files page</p>
    </div>
  )

  const found    = data.rows.filter(r => r.bank_txn_found).length
  const notFound = data.rows.length - found

  return (
    <div>
      {/* Summary strip */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="card p-4 text-center">
          <div className="text-xl font-bold text-amber-600">{fmtINR(data.total_amount)}</div>
          <div className="text-xs text-gray-400 mt-0.5">Total Unsettled Amount</div>
        </div>
        <div className="card p-4 text-center">
          <div className="text-xl font-bold text-green-600">{found}</div>
          <div className="text-xs text-gray-400 mt-0.5">RRNs found in bank report</div>
        </div>
        <div className="card p-4 text-center">
          <div className={`text-xl font-bold ${notFound > 0 ? 'text-red-500' : 'text-gray-400'}`}>{notFound}</div>
          <div className="text-xs text-gray-400 mt-0.5">RRNs NOT found in bank</div>
        </div>
      </div>

      {/* Anomaly table */}
      <div className="card overflow-hidden p-0">
        <div className="px-5 py-3 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-700">Unsettled Transactions (Anomaly RRNs)</span>
          <span className="text-xs text-gray-400">{data.count} entries · {fmtINR(data.total_amount)}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50 text-xs text-gray-400 uppercase tracking-wide">
                <th className="text-left px-4 py-2.5">RRN (Tracking)</th>
                <th className="text-right px-4 py-2.5">Amount</th>
                <th className="text-left px-4 py-2.5">Txn Time</th>
                <th className="text-left px-4 py-2.5">Settled On</th>
                <th className="text-center px-4 py-2.5">In Bank Report?</th>
                <th className="text-left px-4 py-2.5">Bank Eko TID</th>
                <th className="text-center px-4 py-2.5 text-amber-500">Recon Status</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map(r => (
                <tr key={r.id} className={`border-b border-gray-50 hover:bg-gray-50 transition-colors ${!r.bank_txn_found ? 'bg-red-50/30' : ''}`}>
                  <td className="px-4 py-2.5 font-mono text-xs text-gray-700">{r.rrn}</td>
                  <td className="px-4 py-2.5 text-right font-semibold text-amber-600 tabular-nums">{fmtINR(r.amount)}</td>
                  <td className="px-4 py-2.5 text-xs text-gray-500">{r.txn_timestamp}</td>
                  <td className="px-4 py-2.5 text-xs text-gray-500">{r.created_timestamp}</td>
                  <td className="px-4 py-2.5 text-center">
                    {r.bank_txn_found
                      ? <span className="text-green-600 font-medium text-xs flex items-center justify-center gap-1">✓ Found</span>
                      : <span className="text-red-500 font-medium text-xs flex items-center justify-center gap-1">✗ Missing</span>
                    }
                  </td>
                  <td className="px-4 py-2.5 text-xs font-mono text-gray-500">{r.bank_eko_tid || '—'}</td>
                  <td className="px-4 py-2.5 text-center">
                    {r.bank_recon_status === 'unmatched'
                      ? (
                        <div>
                          <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-amber-100 text-amber-700">
                            Anomaly — Pending Settlement
                          </span>
                          <div className="text-xs text-gray-400 mt-0.5">No internal match expected</div>
                        </div>
                      )
                      : r.bank_recon_status === 'matched'
                      ? <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-green-100 text-green-700">matched</span>
                      : r.bank_recon_status
                      ? <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-gray-100 text-gray-600">{r.bank_recon_status}</span>
                      : <span className="text-gray-300 text-xs">—</span>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-4 bg-amber-50 border border-amber-100 rounded-xl p-4 text-xs text-amber-700 space-y-1">
        <p><span className="font-semibold">What "Found in bank report" means: </span>
          The RRN exists as a bank-side transaction in the Fingpay AePS report — the transaction DID happen at the bank.
        </p>
        <p><span className="font-semibold">Why the recon status shows "Anomaly — Pending Settlement": </span>
          Fingpay excluded this transaction from the settlement (3-Way Anomaly deduction). There is no corresponding internal
          Simplibank record to match against — this is intentional. Fingpay will include it in the <em>next</em> settlement cycle.
          The status is correct: it is NOT an error.
        </p>
        <p><span className="font-semibold">Action required: </span>
          Cross-check the total amount against the T Plus 3-Way Anomaly field. Once Fingpay settles these in the next T Plus report, they should clear.
        </p>
      </div>
    </div>
  )
}

// ── CIB / Chargeback Tab ───────────────────────────────────────────────────────

function CibTab({ dateFrom, dateTo }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (dateFrom) params.date_from = dateFrom
      if (dateTo)   params.date_to   = dateTo
      const { data: d } = await api.get('/aeps/cib-list', { params })
      setData(d)
    } catch { toast.error('Failed to load CIB data') }
    finally { setLoading(false) }
  }, [dateFrom, dateTo])

  useEffect(() => { load() }, [load])

  if (loading) return <div className="text-center py-12 text-gray-400 text-sm">Loading…</div>
  if (!data || data.rows.length === 0) return (
    <div className="text-center py-12 text-gray-400">
      <div className="text-4xl mb-3">🔴</div>
      <p className="text-sm font-medium">No CIB / Chargeback entries</p>
      <p className="text-xs mt-1">Upload a CIB report from the Upload Files page</p>
    </div>
  )

  return (
    <div>
      {/* Summary strip */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="card p-4 text-center">
          <div className="text-xl font-bold text-red-600">{fmtINR(data.total_chargeback)}</div>
          <div className="text-xs text-gray-400 mt-0.5">Chargeback Deductions</div>
        </div>
        <div className="card p-4 text-center">
          <div className="text-xl font-bold text-orange-600">{fmtINR(data.total_penalty)}</div>
          <div className="text-xs text-gray-400 mt-0.5">Penalty Deductions</div>
        </div>
        <div className="card p-4 text-center">
          <div className="text-xl font-bold text-red-700 font-bold">{fmtINR(data.total_deduction)}</div>
          <div className="text-xs text-gray-400 mt-0.5">Total CD Deduction</div>
        </div>
      </div>

      {/* CIB table */}
      <div className="card overflow-hidden p-0">
        <div className="px-5 py-3 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-700">Chargebacks & Penalties</span>
          <span className="text-xs text-gray-400">{data.count} entries · {fmtINR(data.total_deduction)}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50 text-xs text-gray-400 uppercase tracking-wide">
                <th className="text-left px-4 py-2.5">Recovery Date</th>
                <th className="text-left px-4 py-2.5">RRN (Tracking)</th>
                <th className="text-right px-4 py-2.5">Amount</th>
                <th className="text-left px-4 py-2.5">Type</th>
                <th className="text-left px-4 py-2.5">Reason</th>
                <th className="text-left px-4 py-2.5">Txn Date</th>
                <th className="text-center px-4 py-2.5">Bank Txn</th>
                <th className="text-left px-4 py-2.5">Bank Eko TID</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map(r => (
                <tr key={r.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-2.5 font-mono text-xs">{r.recovery_date}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-gray-700">{r.rrn}</td>
                  <td className="px-4 py-2.5 text-right font-semibold text-red-600 tabular-nums">{fmtINR(r.amount)}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium
                      ${r.dispute_type === 'CHARGEBACK' ? 'bg-red-100 text-red-700'
                        : r.dispute_type === 'FRAUD' ? 'bg-orange-100 text-orange-700'
                        : 'bg-gray-100 text-gray-600'}`}>
                      {r.dispute_type || r.reason}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-gray-500">{r.reason}</td>
                  <td className="px-4 py-2.5 text-xs text-gray-500">{r.txn_date}</td>
                  <td className="px-4 py-2.5 text-center">
                    {r.bank_txn_found
                      ? <span className="text-green-600 text-xs font-medium">✓ Found</span>
                      : <span className="text-red-500 text-xs font-medium">✗ Missing</span>
                    }
                  </td>
                  <td className="px-4 py-2.5 text-xs font-mono text-gray-500">{r.bank_eko_tid || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-4 bg-red-50 border border-red-100 rounded-xl p-4 text-xs text-red-700">
        <span className="font-semibold">What this means: </span>
        Chargebacks are disputed transactions where the customer or bank reversed payment.
        Penalties are regulatory fines. Both are deducted from your settlement by Fingpay (CD Amount in T Plus).
        Follow up with Fingpay using the RRN for each unresolved entry.
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────

const TABS = [
  { key: 'settlement', label: '📊 T Plus Settlement', desc: 'Verify net settlement formula' },
  { key: 'anomaly',    label: '⚠️  Anomaly RRNs',     desc: 'Unsettled transaction list' },
  { key: 'cib',        label: '🔴 Chargebacks',       desc: 'CIB deductions & penalties' },
]

export default function AepsSettlement({ embedded = false }) {
  const [tab, setTab]         = useState('settlement')
  const [dateFrom, setDateFrom] = useState(monthStart())
  const [dateTo, setDateTo]   = useState(today())
  const [clearing, setClearing] = useState(false)

  const clearAll = async () => {
    if (!window.confirm('Clear ALL AePS settlement data? This cannot be undone.')) return
    setClearing(true)
    try {
      await api.delete('/aeps/clear?report_type=all')
      toast.success('Settlement data cleared')
      setTab(t => t)  // trigger re-render
    } catch { toast.error('Clear failed') } finally { setClearing(false) }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          {!embedded && <h1 className="text-xl font-bold text-gray-800">AePS Settlement Recon</h1>}
          <p className="text-sm text-gray-400">T Plus · Anomaly · Chargeback verification</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={clearAll} disabled={clearing}
            className="btn-ghost flex items-center gap-1.5 text-sm text-red-500 hover:border-red-200">
            <Trash2 size={13} /> Clear Data
          </button>
        </div>
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
              ${tab === t.key
                ? 'border-primary text-primary'
                : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'settlement' && <SettlementTab dateFrom={dateFrom} dateTo={dateTo} />}
      {tab === 'anomaly'    && <AnomalyTab    dateFrom={dateFrom} dateTo={dateTo} />}
      {tab === 'cib'        && <CibTab        dateFrom={dateFrom} dateTo={dateTo} />}
    </div>
  )
}
