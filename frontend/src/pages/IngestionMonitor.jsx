import React, { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Search, Activity } from 'lucide-react'
import toast from 'react-hot-toast'
import api from '../utils/api'

const STATUS_BADGE = {
  completed: 'bg-green-50 text-green-700',
  blocked:   'bg-amber-50 text-amber-700',
  failed:    'bg-red-50 text-red-700',
}

const CHANNEL_BADGE = {
  upload:       { label: '👤 Upload',       cls: 'bg-blue-50 text-blue-700' },
  watch_folder: { label: '🤖 Watch folder', cls: 'bg-purple-50 text-purple-700' },
  auto:         { label: '⚙️ Auto',          cls: 'bg-purple-50 text-purple-700' },
  api:          { label: '🔌 API',           cls: 'bg-indigo-50 text-indigo-700' },
}

const fmtBytes = (n) => {
  if (n == null) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

export default function IngestionMonitor() {
  const [events, setEvents]   = useState([])
  const [total, setTotal]     = useState(0)
  const [page, setPage]       = useState(1)
  const [loading, setLoading] = useState(false)
  const [summary, setSummary] = useState(null)

  const [filters, setFilters] = useState({
    channel: '', status: '', partner: '', from_date: '', to_date: '',
  })

  const load = useCallback(async (p = 1) => {
    setLoading(true)
    try {
      const params = { page: p, page_size: 50, ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) }
      const { data } = await api.get('/ingestion/events', { params })
      setEvents(data.items); setTotal(data.total); setPage(p)
    } catch { toast.error('Failed to load ingestion events') }
    finally { setLoading(false) }
  }, [filters])

  useEffect(() => { load(1) }, [filters])
  useEffect(() => {
    api.get('/ingestion/summary', { params: { days: 7 } }).then(r => setSummary(r.data)).catch(() => {})
  }, [])

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <Activity size={20} className="text-primary" />
          <h1 className="text-xl font-bold text-gray-800">Ingestion Monitor</h1>
        </div>
        <button onClick={() => load(page)} className="btn-ghost flex items-center gap-1.5">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>
      <p className="text-sm text-gray-500 mb-5">
        Lineage of every ingestion attempt across all channels — file fingerprint, row accounting, WLR/FREC outcome.
      </p>

      {/* 7-day summary */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
          <div className="card"><div className="text-xs text-gray-400">Events (7d)</div><div className="text-lg font-bold text-gray-800">{summary.events.toLocaleString()}</div></div>
          <div className="card"><div className="text-xs text-gray-400">Completed</div><div className="text-lg font-bold text-green-700">{(summary.by_status?.completed || 0).toLocaleString()}</div></div>
          <div className="card"><div className="text-xs text-gray-400">Blocked</div><div className="text-lg font-bold text-amber-700">{(summary.by_status?.blocked || 0).toLocaleString()}</div></div>
          <div className="card"><div className="text-xs text-gray-400">Failed</div><div className="text-lg font-bold text-red-700">{(summary.by_status?.failed || 0).toLocaleString()}</div></div>
          <div className="card"><div className="text-xs text-gray-400">Rows skipped (7d)</div><div className="text-lg font-bold text-gray-800">{(summary.rows_skipped || 0).toLocaleString()}</div></div>
        </div>
      )}

      {/* Filters */}
      <div className="card mb-5">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Channel</label>
            <select className="select" value={filters.channel} onChange={e => setFilters({ ...filters, channel: e.target.value })}>
              <option value="">All</option>
              <option value="upload">👤 Upload</option>
              <option value="watch_folder">🤖 Watch folder</option>
              <option value="auto">⚙️ Auto</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Status</label>
            <select className="select" value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })}>
              <option value="">All</option>
              <option value="completed">Completed</option>
              <option value="blocked">Blocked</option>
              <option value="failed">Failed</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Partner</label>
            <input className="input" placeholder="e.g. fino" value={filters.partner}
              onChange={e => setFilters({ ...filters, partner: e.target.value })} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">From Date</label>
            <input type="date" className="input" value={filters.from_date}
              onChange={e => setFilters({ ...filters, from_date: e.target.value })} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">To Date</label>
            <input type="date" className="input" value={filters.to_date}
              onChange={e => setFilters({ ...filters, to_date: e.target.value })} />
          </div>
        </div>
        <div className="flex gap-2 mt-3">
          <button onClick={() => load(1)} className="btn-primary flex items-center gap-1.5"><Search size={14} /> Filter</button>
          <button onClick={() => setFilters({ channel: '', status: '', partner: '', from_date: '', to_date: '' })} className="btn-ghost">Clear</button>
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="table-th">Channel</th>
                <th className="table-th">Status</th>
                <th className="table-th">Timestamp</th>
                <th className="table-th">Partner / Side</th>
                <th className="table-th">File</th>
                <th className="table-th text-right">Read</th>
                <th className="table-th text-right">Accepted</th>
                <th className="table-th text-right">Skipped</th>
                <th className="table-th">WLR/FREC</th>
                <th className="table-th text-right">ms</th>
                <th className="table-th">Details</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={11} className="text-center py-10 text-gray-400">Loading...</td></tr>
              ) : events.length === 0 ? (
                <tr><td colSpan={11} className="text-center py-10 text-gray-400">No ingestion events yet</td></tr>
              ) : (
                events.map(ev => {
                  const ch = CHANNEL_BADGE[ev.channel] || { label: ev.channel || '—', cls: 'bg-gray-100 text-gray-600' }
                  return (
                    <tr key={ev.id} className={`hover:bg-gray-50 border-b border-gray-50 ${ev.status === 'failed' ? 'bg-red-50/30' : ev.status === 'blocked' ? 'bg-amber-50/30' : ''}`}>
                      <td className="table-td"><span className={`text-xs px-1.5 py-0.5 rounded font-medium ${ch.cls}`}>{ch.label}</span></td>
                      <td className="table-td"><span className={`text-xs px-2 py-0.5 rounded font-medium ${STATUS_BADGE[ev.status] || 'bg-gray-100 text-gray-600'}`}>{ev.status || '—'}</span></td>
                      <td className="table-td font-mono text-xs text-gray-500 whitespace-nowrap">{ev.created_at?.replace('T', ' ').slice(0, 19)}</td>
                      <td className="table-td text-xs"><span className="font-medium text-gray-700">{ev.partner || '—'}</span><span className="text-gray-400"> / {ev.side || '—'}</span></td>
                      <td className="table-td text-xs text-gray-600 max-w-[200px] truncate" title={`${ev.filename || ''}\n${ev.file_sha256 || ''}\n${fmtBytes(ev.file_size)}`}>
                        {ev.filename || '—'}
                        {ev.preset_detected && <span className="block text-gray-400">{ev.preset_detected}</span>}
                      </td>
                      <td className="table-td text-right tabular-nums">{ev.rows_read ?? '—'}</td>
                      <td className="table-td text-right tabular-nums">{ev.rows_accepted ?? '—'}</td>
                      <td className={`table-td text-right tabular-nums ${ev.rows_skipped ? 'text-amber-700 font-semibold' : ''}`}>{ev.rows_skipped ?? '—'}</td>
                      <td className="table-td text-xs">
                        <span className={ev.wlr_frec === 'not_checked' ? 'text-amber-700' : 'text-gray-500'}>{ev.wlr_frec || '—'}</span>
                      </td>
                      <td className="table-td text-right tabular-nums text-xs text-gray-500">{ev.duration_ms ?? '—'}</td>
                      <td className="table-td text-xs text-gray-600 max-w-xs">
                        {(ev.detail || ev.skip_breakdown)
                          ? <details className="cursor-pointer">
                              <summary className="text-primary hover:underline">View</summary>
                              <pre className="mt-1 bg-gray-50 rounded p-2 text-xs overflow-auto max-h-40 whitespace-pre-wrap">
                                {JSON.stringify({ detail: ev.detail, skip_breakdown: ev.skip_breakdown, sha256: ev.file_sha256, size: fmtBytes(ev.file_size) }, null, 2)}
                              </pre>
                            </details>
                          : '—'}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {total > 50 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 text-sm">
            <span className="text-gray-500">Showing {((page - 1) * 50) + 1}–{Math.min(page * 50, total)} of {total.toLocaleString()}</span>
            <div className="flex gap-2">
              <button onClick={() => load(page - 1)} disabled={page === 1} className="btn-ghost px-3 py-1 text-xs disabled:opacity-40">Prev</button>
              <button onClick={() => load(page + 1)} disabled={page * 50 >= total} className="btn-ghost px-3 py-1 text-xs disabled:opacity-40">Next</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
