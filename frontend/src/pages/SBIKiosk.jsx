import React, { useState, useEffect, useCallback } from 'react'
import { Upload, Play, CheckCircle, AlertTriangle, Clock, Trash2, RefreshCw, X } from 'lucide-react'
import api from '../utils/api'
import toast from 'react-hot-toast'

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtINR(n) {
  if (n == null || isNaN(n)) return '₹0'
  const abs = Math.abs(Number(n))
  return `₹${abs.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function today() { return new Date().toISOString().split('T')[0] }

const STATUS_COLORS = {
  CREDITED: 'bg-green-100 text-green-700',
  PENDING:  'bg-amber-100 text-amber-700',
  PARTIAL:  'bg-orange-100 text-orange-700',
  EXCESS:   'bg-purple-100 text-purple-700',
  Matched:  'bg-green-100 text-green-700',
  Unmatched:'bg-red-100 text-red-600',
  Unmatched_TxnReport: 'bg-red-100 text-red-600',
  Unmatched_Bank:      'bg-orange-100 text-orange-700',
  Partial:  'bg-amber-100 text-amber-700',
  Reversal: 'bg-purple-100 text-purple-700',
  DEPOSIT:  'bg-red-100 text-red-600',
  WITHDRAWAL:'bg-amber-100 text-amber-700',
  NONE:     'bg-green-100 text-green-700',
}

function StatusBadge({ status }) {
  const cls = STATUS_COLORS[status] || 'bg-gray-100 text-gray-600'
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>{status}</span>
}

function UploadCard({ label, desc, endpoint, extraFields = [], onDone, color = 'blue' }) {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [extra, setExtra] = useState({})
  const fileRef = React.useRef()
  const colorMap = {
    blue:   { border: 'border-blue-300',   bg: 'bg-blue-50',   btn: '#1d4ed8' },
    green:  { border: 'border-green-300',  bg: 'bg-green-50',  btn: '#15803d' },
    purple: { border: 'border-purple-300', bg: 'bg-purple-50', btn: '#7e22ce' },
    amber:  { border: 'border-amber-300',  bg: 'bg-amber-50',  btn: '#d97706' },
  }[color] || {}

  const handleUpload = async () => {
    if (!file) return toast.error('Select a file first')
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      Object.entries(extra).forEach(([k, v]) => { if (v) fd.append(k, v) })
      const { data } = await api.post(endpoint, fd)
      toast.success(`${label}: ${data.inserted} rows uploaded`)
      setFile(null)
      if (onDone) onDone()
    } catch (err) {
      toast.error(err.response?.data?.detail || `${label} upload failed`)
    } finally { setUploading(false) }
  }

  return (
    <div className={`rounded-xl border-2 ${colorMap.border || 'border-gray-200'} ${file ? colorMap.bg : 'bg-white'} p-4 transition-all`}>
      <div className="font-semibold text-gray-800 text-sm mb-1">{label}</div>
      <div className="text-xs text-gray-400 mb-3">{desc}</div>
      {extraFields.map(f => (
        <div key={f.name} className="mb-2">
          <label className="text-xs text-gray-500 block mb-1">{f.label}</label>
          <input type={f.type || 'text'} className="input text-xs" placeholder={f.placeholder}
            onChange={e => setExtra(x => ({...x, [f.name]: e.target.value}))} />
        </div>
      ))}
      <input ref={fileRef} type="file" accept=".xls,.xlsx,.csv" className="hidden"
        onChange={e => { if (e.target.files[0]) setFile(e.target.files[0]) }} />
      <div onClick={() => fileRef.current.click()}
        className="border-2 border-dashed border-gray-200 rounded-lg p-3 text-center cursor-pointer hover:border-gray-400 transition-colors mb-2">
        {file
          ? <div className="flex items-center justify-center gap-2 text-gray-600 text-xs">
              <span className="truncate max-w-[200px]">{file.name}</span>
              <button onClick={e => { e.stopPropagation(); setFile(null) }} className="text-gray-400 hover:text-red-500"><X size={12}/></button>
            </div>
          : <div className="text-gray-400 text-xs"><Upload size={14} className="mx-auto mb-1"/>Click to select</div>
        }
      </div>
      <button onClick={handleUpload} disabled={!file || uploading}
        className="btn-primary w-full text-sm" style={{ background: file ? colorMap.btn : undefined }}>
        {uploading ? 'Uploading…' : `Upload ${label} →`}
      </button>
    </div>
  )
}

// ── Upload Status Panel ────────────────────────────────────────────────────────

function UploadStatus({ onRefresh }) {
  const [status, setStatus] = useState(null)
  const [date, setDate] = useState(today())

  const load = async () => {
    try {
      const { data } = await api.get('/sbi/upload-status', { params: { upload_date: date } })
      setStatus(data)
    } catch { }
  }

  useEffect(() => { load() }, [date])

  const items = status ? [
    { label: 'Bank Statement', key: 'bank_statement', icon: '🏦' },
    { label: 'Transaction Reports', key: 'txn_reports', icon: '📋' },
    { label: 'KO Limits Config', key: 'ko_limits', icon: '⚙️' },
    { label: 'KO Cash Holding', key: 'ko_cash_holding', icon: '💰' },
    { label: 'Limit Failures', key: 'limit_failures', icon: '⚠️' },
    { label: 'CSP Master', key: 'csp_master', icon: '📊' },
  ] : []

  return (
    <div className="card mb-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-700 text-sm">Upload Status</h3>
        <div className="flex items-center gap-2">
          <input type="date" className="input text-xs w-36" value={date} onChange={e => setDate(e.target.value)} />
          <button onClick={load} className="btn-ghost flex items-center gap-1 text-xs"><RefreshCw size={12}/>Refresh</button>
        </div>
      </div>
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
        {items.map(({ label, key, icon }) => (
          <div key={key} className={`text-center p-2 rounded-lg text-xs ${(status?.[key] || 0) > 0 ? 'bg-green-50 border border-green-200' : 'bg-gray-50 border border-gray-200'}`}>
            <div className="text-lg">{icon}</div>
            <div className={`font-bold ${(status?.[key] || 0) > 0 ? 'text-green-700' : 'text-gray-400'}`}>{(status?.[key] || 0).toLocaleString()}</div>
            <div className="text-gray-500 leading-tight">{label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── P01 Tab ────────────────────────────────────────────────────────────────────

function P01Tab() {
  const [reconDate, setReconDate] = useState(today())
  const [running, setRunning] = useState(false)
  const [data, setData] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')

  const runRecon = async () => {
    setRunning(true)
    try {
      const { data: r } = await api.post('/sbi/run/p01', null, { params: { recon_date: reconDate } })
      toast.success(`P01 complete: ${r.summary.CREDITED || 0} credited, ${r.summary.PENDING || 0} pending`)
      loadResults()
    } catch (err) { toast.error(err.response?.data?.detail || 'P01 failed') }
    finally { setRunning(false) }
  }

  const loadResults = useCallback(async () => {
    try {
      const { data: d } = await api.get('/sbi/p01/results', { params: { recon_date: reconDate, ...(statusFilter && { status: statusFilter }) } })
      setData(d)
    } catch { }
  }, [reconDate, statusFilter])

  useEffect(() => { loadResults() }, [loadResults])

  const g = data?.grand || {}

  return (
    <div>
      <div className="card mb-4 bg-blue-50 border border-blue-100 p-4 text-xs text-blue-700">
        <strong>Process 01 — SBI Settlement Reconciliation:</strong> Matches KO wallet withdrawals (Limits Config) against
        bank settlement credits (EKOSETTLEMENT in bank statement). KO ID is the match key.
        D+1 logic: deduction date in description may differ from bank transaction date.
      </div>
      <div className="flex items-center gap-3 mb-5">
        <div>
          <label className="text-xs text-gray-400 block mb-1">Recon Date</label>
          <input type="date" className="input" value={reconDate} onChange={e => setReconDate(e.target.value)} />
        </div>
        <div className="self-end">
          <button onClick={runRecon} disabled={running}
            className="btn-primary flex items-center gap-2">
            <Play size={14}/>{running ? 'Running…' : 'Run P01 Settlement Recon'}
          </button>
        </div>
        <div className="self-end">
          <select className="select text-sm" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
            <option value="">All Statuses</option>
            {['CREDITED','PENDING','PARTIAL','EXCESS'].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>

      {data && (
        <>
          <div className="grid grid-cols-4 gap-3 mb-5">
            {[
              { label: 'Wallet Withdrawn', value: fmtINR(g.wallet_withdrawn), color: 'text-gray-800' },
              { label: 'Bank Settled',     value: fmtINR(g.bank_settled),     color: 'text-green-700' },
              { label: 'Difference',       value: fmtINR(g.difference),       color: Math.abs(g.difference||0) < 1 ? 'text-green-600' : 'text-red-500' },
              { label: 'Total KOs',        value: data.count,                  color: 'text-gray-800' },
            ].map(({ label, value, color }) => (
              <div key={label} className="card p-4 text-center">
                <div className={`text-lg font-bold ${color}`}>{value}</div>
                <div className="text-xs text-gray-400">{label}</div>
              </div>
            ))}
          </div>

          <div className="card overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50/50 text-xs text-gray-400 uppercase tracking-wide">
                    <th className="text-left px-4 py-2.5">KO ID</th>
                    <th className="text-right px-4 py-2.5">Wallet Withdrawn</th>
                    <th className="text-right px-4 py-2.5">Bank Settled</th>
                    <th className="text-right px-4 py-2.5">Difference</th>
                    <th className="text-center px-4 py-2.5">Status</th>
                    <th className="text-left px-4 py-2.5">Deduction Date</th>
                    <th className="text-left px-4 py-2.5">Bank Date</th>
                    <th className="text-left px-4 py-2.5">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map(r => (
                    <tr key={r.id} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="px-4 py-2.5 font-mono text-xs font-semibold">{r.ko_id}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{fmtINR(r.wallet_withdrawn)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-green-600">{fmtINR(r.bank_settled)}</td>
                      <td className={`px-4 py-2.5 text-right tabular-nums ${Math.abs(r.difference||0) > 0.01 ? 'text-red-500 font-semibold' : 'text-gray-400'}`}>{fmtINR(r.difference)}</td>
                      <td className="px-4 py-2.5 text-center"><StatusBadge status={r.status}/></td>
                      <td className="px-4 py-2.5 text-xs font-mono text-gray-500">{r.deduct_date}</td>
                      <td className="px-4 py-2.5 text-xs font-mono text-gray-500">{r.bank_txn_date}</td>
                      <td className="px-4 py-2.5 text-xs text-gray-400 italic">{r.notes}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ── P02 Tab ────────────────────────────────────────────────────────────────────

function P02Tab() {
  const [reconDate, setReconDate] = useState(today())
  const [running, setRunning] = useState(false)
  const [data, setData] = useState(null)
  const [filter, setFilter] = useState('')

  const runRecon = async () => {
    setRunning(true)
    try {
      const { data: r } = await api.post('/sbi/run/p02', null, { params: { recon_date: reconDate } })
      toast.success(`P02: ${r.summary.Matched||0} matched, ${r.summary.Unmatched||0} unmatched, ${r.summary.Reversal||0} reversals`)
      loadResults()
    } catch (err) { toast.error(err.response?.data?.detail || 'P02 failed') }
    finally { setRunning(false) }
  }

  const loadResults = useCallback(async () => {
    try {
      const { data: d } = await api.get('/sbi/p02/results', { params: { recon_date: reconDate, ...(filter && { match_status: filter }) } })
      setData(d)
    } catch { }
  }, [reconDate, filter])

  useEffect(() => { loadResults() }, [loadResults])

  return (
    <div>
      <div className="card mb-4 bg-green-50 border border-green-100 p-4 text-xs text-green-700">
        <strong>Process 02 — Bank Statement & Transaction Report Reconciliation:</strong> Matches 7 transaction report files
        against the bank statement using 20-digit Reference Number extracted from bank description.
        Reversal detection: same reference appears as both Debit and Credit.
      </div>
      <div className="flex items-center gap-3 mb-5">
        <div><label className="text-xs text-gray-400 block mb-1">Recon Date</label>
          <input type="date" className="input" value={reconDate} onChange={e => setReconDate(e.target.value)} />
        </div>
        <div className="self-end">
          <button onClick={runRecon} disabled={running} className="btn-primary flex items-center gap-2">
            <Play size={14}/>{running ? 'Running…' : 'Run P02 Recon'}
          </button>
        </div>
        <div className="self-end">
          <select className="select text-sm" value={filter} onChange={e => setFilter(e.target.value)}>
            <option value="">All</option>
            {['Matched','Unmatched','Partial','Reversal'].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>

      {data && (
        <>
          <div className="flex gap-3 mb-5 flex-wrap">
            {Object.entries(data.summary).map(([k, v]) => (
              <div key={k} className="card p-3 text-center min-w-[100px]">
                <div className="text-xl font-bold text-gray-800">{v}</div>
                <StatusBadge status={k}/>
              </div>
            ))}
          </div>
          <div className="card overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50/50 text-gray-400 uppercase tracking-wide">
                    <th className="text-left px-3 py-2">Reference Number</th>
                    <th className="text-left px-3 py-2">KO ID</th>
                    <th className="text-right px-3 py-2">Bank Amount</th>
                    <th className="text-center px-3 py-2">DR/CR</th>
                    <th className="text-right px-3 py-2">Report Amount</th>
                    <th className="text-left px-3 py-2">Txn Type</th>
                    <th className="text-center px-3 py-2">Match</th>
                    <th className="text-center px-3 py-2">Reversal</th>
                    <th className="text-center px-3 py-2">Status</th>
                    <th className="text-left px-3 py-2">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.slice(0, 500).map(r => (
                    <tr key={r.id} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="px-3 py-2 font-mono text-gray-600">{r.reference_number?.slice(-10) || '—'}</td>
                      <td className="px-3 py-2 font-mono">{r.ko_id}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmtINR(r.bank_amount)}</td>
                      <td className="px-3 py-2 text-center">
                        <span className={`font-medium ${r.bank_type === 'DR' ? 'text-red-500' : 'text-green-600'}`}>{r.bank_type}</span>
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-gray-500">{r.report_amount != null ? fmtINR(r.report_amount) : '—'}</td>
                      <td className="px-3 py-2 text-gray-500 max-w-[140px] truncate">{r.report_txn_type || r.notes}</td>
                      <td className="px-3 py-2 text-center"><StatusBadge status={r.match_status}/></td>
                      <td className="px-3 py-2 text-center text-xs text-gray-500">{r.reversal_type || '—'}</td>
                      <td className="px-3 py-2 text-center"><span className={`text-xs font-medium ${r.success_status === 'Success' ? 'text-green-600' : 'text-red-500'}`}>{r.success_status}</span></td>
                      <td className="px-3 py-2 text-gray-500 max-w-[180px]"><span className="block truncate" title={r.bank_description || ''}>{r.bank_description || '—'}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.count > 500 && <div className="px-4 py-2 text-xs text-gray-400 text-center">Showing 500 of {data.count} rows — use status filter to narrow down</div>}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ── P03 Tab ────────────────────────────────────────────────────────────────────

function P03Tab() {
  const [reconDate, setReconDate] = useState(today())
  const [running, setRunning] = useState(false)
  const [data, setData] = useState(null)
  const [filter, setFilter] = useState('')

  const runRecon = async () => {
    setRunning(true)
    try {
      const { data: r } = await api.post('/sbi/run/p03', null, { params: { recon_date: reconDate } })
      toast.success(`P03: ${r.summary.Matched||0} matched, ${r.summary.Unmatched_TxnReport||0} unmatched`)
      loadResults()
    } catch (err) { toast.error(err.response?.data?.detail || 'P03 failed') }
    finally { setRunning(false) }
  }

  const loadResults = useCallback(async () => {
    try {
      const { data: d } = await api.get('/sbi/p03/results', { params: { recon_date: reconDate, ...(filter && { match_status: filter }) } })
      setData(d)
    } catch { }
  }, [reconDate, filter])

  useEffect(() => { loadResults() }, [loadResults])

  const PRIORITY_LABELS = { 1: 'Same day', 2: 'D+1 (bank)', 3: 'D+1 (txn)', 4: 'D-1' }

  return (
    <div>
      <div className="card mb-4 bg-purple-50 border border-purple-100 p-4 text-xs text-purple-700">
        <strong>Process 03 — CSP-Transaction-Bank Reconciliation:</strong> Matches money paid OUT to CSPs (Transaction Report debits)
        vs money received IN from CSPs (Bank Statement credits). Match key: CSP Code + Amount.
        4-priority date shifting: Same day → D+1 bank → D+1 txn → D-1. One-to-one matching only.
      </div>
      <div className="flex items-center gap-3 mb-5">
        <div><label className="text-xs text-gray-400 block mb-1">Recon Date</label>
          <input type="date" className="input" value={reconDate} onChange={e => setReconDate(e.target.value)} />
        </div>
        <div className="self-end">
          <button onClick={runRecon} disabled={running} className="btn-primary flex items-center gap-2" style={{background:'#7c3aed'}}>
            <Play size={14}/>{running ? 'Running…' : 'Run P03 Recon'}
          </button>
        </div>
        <div className="self-end">
          <select className="select text-sm" value={filter} onChange={e => setFilter(e.target.value)}>
            <option value="">All</option>
            {['Matched','Unmatched_TxnReport','Unmatched_Bank'].map(s => <option key={s} value={s}>{s.replace('_',' ')}</option>)}
          </select>
        </div>
      </div>

      {data && (
        <>
          <div className="flex gap-3 mb-5 flex-wrap">
            {Object.entries(data.summary).map(([k, v]) => (
              <div key={k} className="card p-3 text-center min-w-[130px]">
                <div className="text-xl font-bold text-gray-800">{v}</div>
                <StatusBadge status={k}/>
              </div>
            ))}
          </div>
          <div className="card overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50/50 text-gray-400 uppercase tracking-wide">
                    <th className="text-left px-3 py-2">CSP Code</th>
                    <th className="text-left px-3 py-2">Mode</th>
                    <th className="text-right px-3 py-2">Txn Amount</th>
                    <th className="text-left px-3 py-2">Txn Date</th>
                    <th className="text-right px-3 py-2">Bank Credit</th>
                    <th className="text-left px-3 py-2">Bank Date</th>
                    <th className="text-center px-3 py-2">Match</th>
                    <th className="text-center px-3 py-2">Date Shift</th>
                    <th className="text-left px-3 py-2">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.slice(0, 500).map(r => (
                    <tr key={r.id} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="px-3 py-2 font-mono font-semibold">{r.csp_code}</td>
                      <td className="px-3 py-2 text-gray-500">{r.mode}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{r.txn_amount != null ? fmtINR(r.txn_amount) : '—'}</td>
                      <td className="px-3 py-2 font-mono text-gray-500">{r.txn_date || '—'}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-green-600">{r.bank_amount != null ? fmtINR(r.bank_amount) : '—'}</td>
                      <td className="px-3 py-2 font-mono text-gray-500">{r.bank_credit_date || '—'}</td>
                      <td className="px-3 py-2 text-center"><StatusBadge status={r.match_status}/></td>
                      <td className="px-3 py-2 text-center text-gray-500">
                        {r.date_shift != null ? <span title={PRIORITY_LABELS[r.match_priority]}>{r.date_shift > 0 ? `+${r.date_shift}d` : r.date_shift === 0 ? '0' : `${r.date_shift}d`}</span> : '—'}
                      </td>
                      <td className="px-3 py-2 text-gray-400 italic">{r.notes}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ── P04 Tab ────────────────────────────────────────────────────────────────────

function P04Tab({ onRefresh }) {
  const [reconDate, setReconDate] = useState(today())
  const [running, setRunning] = useState(false)
  const [data, setData] = useState(null)
  const [filter, setFilter] = useState('')

  const runRecon = async () => {
    setRunning(true)
    try {
      const { data: r } = await api.post('/sbi/run/p04', null, { params: { recon_date: reconDate } })
      toast.success(`P04: ${r.summary.DEPOSIT||0} need deposit, ${r.summary.WITHDRAWAL||0} need withdrawal`)
      loadResults()
    } catch (err) { toast.error(err.response?.data?.detail || 'P04 failed') }
    finally { setRunning(false) }
  }

  const loadResults = useCallback(async () => {
    try {
      const { data: d } = await api.get('/sbi/p04/results', { params: { recon_date: reconDate, ...(filter && { action_required: filter }) } })
      setData(d)
    } catch { }
  }, [reconDate, filter])

  useEffect(() => { loadResults() }, [loadResults])

  const markDone = async (id, done) => {
    try {
      await api.patch(`/sbi/p04/${id}/done`, null, { params: { done } })
      toast.success(done ? 'Marked as done' : 'Marked as pending')
      loadResults()
    } catch { toast.error('Update failed') }
  }

  return (
    <div>
      <div className="card mb-4 bg-amber-50 border border-amber-100 p-4 text-xs text-amber-700">
        <strong>Process 04 — CSP Wallet Balance Reconciliation:</strong> Identifies wallet discrepancies from
        Limit Update Failure Report vs KO Cash Holding. Flags which CSPs need DEPOSIT or WITHDRAWAL
        adjustment in the SBI portal. Team marks done after performing the action.
      </div>
      <div className="flex items-center gap-3 mb-5">
        <div><label className="text-xs text-gray-400 block mb-1">Recon Date</label>
          <input type="date" className="input" value={reconDate} onChange={e => setReconDate(e.target.value)} />
        </div>
        <div className="self-end">
          <button onClick={runRecon} disabled={running} className="btn-primary flex items-center gap-2" style={{background:'#d97706'}}>
            <Play size={14}/>{running ? 'Running…' : 'Run P04 Recon'}
          </button>
        </div>
        <div className="self-end">
          <select className="select text-sm" value={filter} onChange={e => setFilter(e.target.value)}>
            <option value="">All Actions</option>
            {['DEPOSIT','WITHDRAWAL','NONE'].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>

      {data && data.rows.length === 0 && (
        <div className="text-center py-10 text-gray-400 text-sm">No results — run P04 recon first</div>
      )}

      {data && data.rows.length > 0 && (
        <div className="card overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50 text-xs text-gray-400 uppercase tracking-wide">
                  <th className="text-left px-4 py-2.5">CSP Code</th>
                  <th className="text-right px-4 py-2.5">Failed Amount</th>
                  <th className="text-right px-4 py-2.5">Closing Balance</th>
                  <th className="text-right px-4 py-2.5">Expected</th>
                  <th className="text-right px-4 py-2.5">Difference</th>
                  <th className="text-center px-4 py-2.5">Action</th>
                  <th className="text-right px-4 py-2.5">Amount</th>
                  <th className="text-center px-4 py-2.5">Done?</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map(r => (
                  <tr key={r.id} className={`border-b border-gray-50 hover:bg-gray-50 ${r.action_done ? 'opacity-50' : ''}`}>
                    <td className="px-4 py-2.5 font-mono font-semibold">{r.csp_code}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{fmtINR(r.failed_amount)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{fmtINR(r.closing_balance)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-gray-500">{fmtINR(r.expected_balance)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums font-semibold text-red-500">{fmtINR(r.difference)}</td>
                    <td className="px-4 py-2.5 text-center"><StatusBadge status={r.action_required}/></td>
                    <td className="px-4 py-2.5 text-right tabular-nums font-bold">{fmtINR(r.action_amount)}</td>
                    <td className="px-4 py-2.5 text-center">
                      <button
                        onClick={() => markDone(r.id, !r.action_done)}
                        className={`text-xs px-2 py-0.5 rounded-full border font-medium transition-colors ${r.action_done ? 'bg-green-100 text-green-700 border-green-300' : 'bg-gray-100 text-gray-500 border-gray-300 hover:bg-green-50'}`}>
                        {r.action_done ? '✓ Done' : 'Mark Done'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-3 text-xs text-amber-700 bg-amber-50 border-t border-amber-100">
            After performing each action in the SBI Browser Portal, click "Mark Done" to track completion.
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────

const PROCESSES = [
  { key: 'p01', label: '💳 P01 Settlement',     color: 'blue'   },
  { key: 'p02', label: '📊 P02 Bank+Txn Report', color: 'green'  },
  { key: 'p03', label: '🔄 P03 CSP-Txn-Bank',   color: 'purple' },
  { key: 'p04', label: '⚖️ P04 Wallet Balance',  color: 'amber'  },
]

export default function SBIKiosk() {
  const [tab, setTab] = useState('upload')
  const [uploadKey, setUploadKey] = useState(0)
  const onUploadDone = () => setUploadKey(k => k + 1)

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-bold text-gray-800">SBI Kiosk Banking Recon</h1>
          <p className="text-sm text-gray-400">
            Upload the four process files in the <span className="font-medium">Upload</span> tab, then run P01–P04.
          </p>
        </div>
      </div>

      {/* Upload status summary */}
      <UploadStatus />

      {/* Tab bar */}
      <div className="flex gap-0 mb-5 border-b border-gray-200 overflow-x-auto">
        <button key="upload" onClick={() => setTab('upload')}
          className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap
            ${tab === 'upload' ? 'border-primary text-primary' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
          ⬆ Upload
        </button>
        {PROCESSES.map(p => (
          <button key={p.key} onClick={() => setTab(p.key)}
            className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap
              ${tab === p.key ? 'border-primary text-primary' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {p.label}
          </button>
        ))}
      </div>

      {/* Upload tab — card-style uploads for all four processes */}
      {tab === 'upload' && (
        <div className="space-y-6">
          <UploadStatus key={uploadKey} />

          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-bold text-blue-700 bg-blue-100 px-2.5 py-1 rounded-full uppercase tracking-wide">P01 — Settlement Recon</span>
            </div>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <UploadCard label="Bank Statement" desc="SBI settlement account .xls (tab-separated)" endpoint="/sbi/upload/bank-statement" onDone={onUploadDone} color="blue"/>
              <UploadCard label="KO Limits Config Report" desc="KO_Limits_Configuration_Report_*.xls" endpoint="/sbi/upload/ko-limits" onDone={onUploadDone} color="blue"/>
            </div>
          </div>

          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-bold text-green-700 bg-green-100 px-2.5 py-1 rounded-full uppercase tracking-wide">P02 — Bank + Transaction Report Recon</span>
              <span className="text-xs text-gray-400">Upload all 7 transaction report files one at a time</span>
            </div>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <UploadCard label="Transaction Report File" desc="Any of the 7 BC Transaction Report files (AEPS, Withdrawal, Deposit, Money Transfer, etc.)" endpoint="/sbi/upload/txn-report" onDone={onUploadDone} color="green"/>
            </div>
          </div>

          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-bold text-purple-700 bg-purple-100 px-2.5 py-1 rounded-full uppercase tracking-wide">P03 — CSP-Transaction-Bank Recon</span>
            </div>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <UploadCard label="CSP Master Sheet" desc="CSP Code | Ref Number | Mode (Cash/CDM/Electronic)" endpoint="/sbi/upload/csp-master" onDone={onUploadDone} color="purple"/>
            </div>
          </div>

          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-bold text-amber-700 bg-amber-100 px-2.5 py-1 rounded-full uppercase tracking-wide">P04 — Wallet Balance Recon</span>
            </div>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <UploadCard label="KO Cash Holding Report" desc="KO_Cash_Holding_Report_*.xls — opening/closing wallet balances" endpoint="/sbi/upload/ko-cash-holding" onDone={onUploadDone} color="amber"
                extraFields={[{ name: 'report_date', label: 'Report Date', type: 'date', placeholder: 'YYYY-MM-DD' }]}/>
              <UploadCard label="Limit Update Failure Report" desc="Limit_Fail_*.xls — KOs whose wallet limit update failed" endpoint="/sbi/upload/limit-failures" onDone={onUploadDone} color="amber"/>
            </div>
          </div>
        </div>
      )}

      {/* end false block */}

      {tab === 'p01' && <P01Tab />}
      {tab === 'p02' && <P02Tab />}
      {tab === 'p03' && <P03Tab />}
      {tab === 'p04' && <P04Tab />}
    </div>
  )
}
