import React, { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Download, Search, RefreshCw, Tag, X, Trash2, Tags, Banknote, ArrowLeftRight, ShieldAlert } from 'lucide-react'
import toast from 'react-hot-toast'
import api from '../utils/api'
import { isOpenItemsPartner } from '../productRegistry'
import { STATUS_GROUPS, groupEnabled, statusEnabled, STATUS_LABEL_BY_VALUE, fieldApplies } from '../filterModel'

// Fallback partner list — used only if the API is unavailable
const FALLBACK_PARTNERS = [
  { slug: 'fino',      display_name: 'Fino'      },
  { slug: 'airtel',    display_name: 'Airtel'    },
  { slug: 'axis',      display_name: 'Axis'      },
  { slug: 'levin',     display_name: 'Levin'     },
  { slug: 'aeps',      display_name: 'AePS'      },
  { slug: 'pg',        display_name: 'PG'        },
  { slug: 'digikhata', display_name: 'Digikhata' },
  { slug: 'indonepal', display_name: 'Indo-Nepal' },
  { slug: 'evalue',    display_name: 'E-Value' },
  { slug: 'bbps',      display_name: 'BBPS' },
]

const STATUS_BADGE = {
  unmatched:           'badge-red',
  src_assigned:        'badge-yellow',
  matched:             'badge-green',
  manual_matched:      'badge-blue',
  fee_matched:         'badge-blue',
  fund_transfer:       'badge-blue',
  interbank_matched:   'badge-purple',
  adhoc_settlement:    'badge-orange',
  amount_mismatch:     'badge-orange',
  duplicate:           'badge-red',
  failed:              'badge-gray',
  reversal_matched:    'badge-purple',
}

const AGING_BADGE = {
  'current': { label: 'Today',  cls: 'bg-blue-50 text-blue-600' },
  'D+1':     { label: 'D+1',    cls: 'bg-amber-50 text-amber-600' },
  'D+3':     { label: 'D+3',    cls: 'bg-orange-50 text-orange-700' },
  'D+7+':    { label: 'D+7+',   cls: 'bg-red-100 text-red-700 font-bold' },
}

const SRC_CODES = [
  'UNCLAIMED','ADVANCE_CREDIT','BANK_CHARGES','TWICE_CREDITED',
  'INTERNAL_TXN','DELAYED_TXN','DUPLICATE','MISSING_TID','OTHER'
]

const COLS = 16  // checkbox + 14 data cols + actions

export default function OpenItems() {
  const [searchParams] = useSearchParams()

  const initReconDate = searchParams.get('recon_date') || ''
  const initFilters = {
    partner:          searchParams.get('partner') || '',
    recon_date:       initReconDate,
    date_from:        initReconDate ? '' : (searchParams.get('date_from') || ''),
    date_to:          initReconDate ? '' : (searchParams.get('date_to') || ''),
    side:             searchParams.get('side') || '',
    src_code:         '',
    eko_tid:          '',
    tracking_number:  '',
    match_id:         '',
    recon_status:     searchParams.get('recon_status') || '',
    aging:            '',
    amount_min:       '',
    amount_max:       '',
    bank_account:     searchParams.get('bank_account') || '',
  }

  // ── All useState hooks FIRST — no hooks after this block ────────────────────
  const [filters, setFilters]             = useState(initFilters)
  const [items, setItems]                 = useState([])
  const [total, setTotal]                 = useState(0)
  const [page, setPage]                   = useState(1)
  const [loading, setLoading]             = useState(false)
  const [partnerList, setPartnerList]     = useState(FALLBACK_PARTNERS)
  const [bankAccounts, setBankAccounts]   = useState([])
  const [srcModal, setSrcModal]           = useState(null)
  const [srcForm, setSrcForm]             = useState({ src_code: '', src_note: '' })
  const [bulkSrcOpen, setBulkSrcOpen]     = useState(false)
  const [bulkForm, setBulkForm]           = useState({ src_code: '', src_note: '' })
  const [bulkSaving, setBulkSaving]       = useState(false)
  const [adhocModal, setAdhocModal]       = useState(null)
  const [adhocRemark, setAdhocRemark]     = useState('')
  const [adhocSaving, setAdhocSaving]     = useState(false)
  const [overrideModal, setOverrideModal] = useState(null)
  const [interbankSelect, setInterbankSelect] = useState(null)
  const [interbankModal, setInterbankModal]   = useState(null)
  const [selected, setSelected]           = useState(new Set())
  const [deleting, setDeleting]           = useState(false)
  const [bulkOverrideOpen, setBulkOverrideOpen] = useState(false)
  const [bulkOverrideForm, setBulkOverrideForm] = useState({ new_status: 'unmatched', remark: '' })
  const [bulkOverrideSaving, setBulkOverrideSaving] = useState(false)

  // ── Derived values (no hooks below) ─────────────────────────────────────────
  // permissions may be stored as an object or a JSON string — handle both safely
  const currentUser = (() => { try { return JSON.parse(localStorage.getItem('user') || '{}') } catch { return {} } })()
  const _perms      = (() => { try { const p = currentUser.permissions; if (!p) return {}; return typeof p === 'object' ? p : JSON.parse(p) } catch { return {} } })()
  const hasOverride = currentUser.role === 'admin' || _perms.override === true

  useEffect(() => {
    api.get('/admin/partners-public')
      .then(({ data }) => { const list = (data || []).filter(isOpenItemsPartner); if (list.length) setPartnerList(list) })
      .catch(() => {})
    api.get('/admin/bank-accounts')
      .then(({ data }) => setBankAccounts(data || []))
      .catch(() => {})
  }, [])

  const load = useCallback(async (p = 1) => {
    setLoading(true)
    setSelected(new Set())
    try {
      const params = { page: p, page_size: 50, ...Object.fromEntries(Object.entries(filters).filter(([,v]) => v)) }
      const { data } = await api.get('/recon/open-items', { params })
      setItems(data.items ?? []); setTotal(data.total ?? 0); setPage(p)
    } catch { toast.error('Failed to load') }
    finally { setLoading(false) }
  }, [filters])

  useEffect(() => { load(1) }, [filters])

  // Browser tab title reflects active filter
  useEffect(() => {
    const parts = ['Open Items']
    if (filters.partner) parts.push(filters.partner.charAt(0).toUpperCase() + filters.partner.slice(1))
    if (filters.recon_status) parts.push(filters.recon_status.replace(/_/g,' '))
    document.title = parts.join(' — ') + ' | Eko Recon'
    return () => { document.title = 'Eko Bharat Ventures — Recon' }
  }, [filters.partner, filters.recon_status])

  const handleExport = async () => {
    try {
      const params = new URLSearchParams(Object.fromEntries(Object.entries(filters).filter(([,v]) => v)))
      const resp = await api.get(`/reports/open-items/export?${params}`, { responseType: 'blob' })
      const url = URL.createObjectURL(resp.data)
      const a = document.createElement('a'); a.href = url; a.download = 'open_items.xlsx'; a.click()
      toast.success('Downloaded')
    } catch { toast.error('Export failed') }
  }

  // ── Single SRC assign ─────────────────────────────────────────────────────
  const handleAssignSrc = async () => {
    if (!srcForm.src_code) return toast.error('Select a SRC code')
    try {
      await api.post('/recon/assign-src', { transaction_id: srcModal.id, ...srcForm })
      toast.success('SRC assigned')
      setSrcModal(null)
      load(page)
    } catch { toast.error('Failed') }
  }

  // ── Bulk SRC assign ───────────────────────────────────────────────────────
  const handleBulkSrc = async () => {
    if (!bulkForm.src_code) return toast.error('Select a SRC code')
    setBulkSaving(true)
    try {
      const { data } = await api.post('/recon/assign-src-bulk', {
        transaction_ids: [...selected],
        src_code:        bulkForm.src_code,
        src_note:        bulkForm.src_note,
      })
      toast.success(`SRC assigned to ${data.updated} transaction(s)`)
      setBulkSrcOpen(false)
      setBulkForm({ src_code: '', src_note: '' })
      load(page)
    } catch { toast.error('Bulk SRC failed') }
    finally { setBulkSaving(false) }
  }

  // ── Bulk Override ─────────────────────────────────────────────────────────
  const handleBulkOverride = async () => {
    if (!bulkOverrideForm.remark.trim()) return toast.error('Remark is required')
    setBulkOverrideSaving(true)
    try {
      const { data } = await api.post('/recon/bulk-override-status', {
        transaction_ids: [...selected],
        new_status: bulkOverrideForm.new_status,
        remark: bulkOverrideForm.remark.trim(),
      })
      toast.success(data.message)
      setBulkOverrideOpen(false)
      setBulkOverrideForm({ new_status: 'unmatched', remark: '' })
      load(page)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Bulk override failed')
    } finally { setBulkOverrideSaving(false) }
  }

  // ── Checkbox selection ────────────────────────────────────────────────────
  const toggleRow = (id) => {
    setSelected(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n })
  }
  const toggleAll = () => {
    setSelected(selected.size === items.length ? new Set() : new Set(items.map(i => i.id)))
  }

  // ── Adhoc Settlement tag ──────────────────────────────────────────────────
  const handleTagAdhoc = async () => {
    if (!adhocRemark.trim()) return toast.error('Remark is required for adhoc settlement')
    setAdhocSaving(true)
    try {
      await api.post('/recon/tag-adhoc', { transaction_id: adhocModal.id, remark: adhocRemark.trim() })
      toast.success('Tagged as adhoc settlement')
      setAdhocModal(null)
      setAdhocRemark('')
      load(page)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to tag adhoc')
    } finally { setAdhocSaving(false) }
  }

  const handleDeleteSelected = async () => {
    if (selected.size === 0) return
    if (!window.confirm(`Delete ${selected.size} selected transaction(s)? This cannot be undone.`)) return
    setDeleting(true)
    try {
      const ids = [...selected].join(',')
      const { data } = await api.delete(`/upload/clear-selected?transaction_ids=${ids}`)
      toast.success(`Deleted ${data.deleted_transactions} transactions`)
      load(page)
    } catch { toast.error('Delete failed') }
    finally { setDeleting(false) }
  }

  const pageTitle = STATUS_LABEL_BY_VALUE[filters.recon_status] || 'Open Items'

  // When the partner changes, a previously-chosen status may no longer apply
  // (e.g. a DMT-only status while BBPS is selected) — fall back to Open Items.
  const onPartnerChange = (slug) => {
    setFilters(f => ({
      ...f,
      partner: slug,
      recon_status: statusEnabled(f.recon_status, slug) ? f.recon_status : '',
      src_code: fieldApplies('src_code', slug) ? f.src_code : '',
    }))
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-bold text-gray-800">{pageTitle}</h1>
        <div className="flex gap-2 flex-wrap">
          {selected.size > 0 && (
            <>
              <button onClick={() => setBulkSrcOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-yellow-50 text-yellow-700 hover:bg-yellow-100 border border-yellow-200 transition-colors">
                <Tags size={14} /> Assign SRC ({selected.size})
              </button>
              {hasOverride && (
                <button onClick={() => setBulkOverrideOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-red-50 text-red-600 hover:bg-red-100 border border-red-200 transition-colors">
                  <ShieldAlert size={14} /> Bulk Override ({selected.size})
                </button>
              )}
              <button onClick={handleDeleteSelected} disabled={deleting}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-red-50 text-red-600 hover:bg-red-100 border border-red-200 transition-colors disabled:opacity-50">
                <Trash2 size={14} /> {deleting ? 'Deleting...' : `Delete ${selected.size}`}
              </button>
            </>
          )}
          <button onClick={() => load(1)} className="btn-ghost flex items-center gap-1.5">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
          <button onClick={handleExport} className="btn-primary flex items-center gap-1.5">
            <Download size={14} /> Export Excel
          </button>
        </div>
      </div>
      <p className="text-sm text-gray-500 mb-5">
        {total.toLocaleString()} transactions
        {selected.size > 0 && <span className="ml-2 text-primary font-medium">{selected.size} selected</span>}
      </p>

      {/* Filters */}
      <div className="card mb-5">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-10 gap-3">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Status</label>
            <select className="select" value={filters.recon_status} onChange={e => setFilters({...filters, recon_status: e.target.value})}>
              {STATUS_GROUPS.map(g => (
                <optgroup key={g.label} label={g.label}>
                  {g.options.map(o => (
                    <option key={`${g.label}-${o.v}`} value={o.v} disabled={!groupEnabled(g.scope, filters.partner)}>
                      {o.l}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Partner</label>
            <select className="select" value={filters.partner} onChange={e => onPartnerChange(e.target.value)}>
              <option value="">All</option>
              {partnerList.map(p => (
                <option key={p.slug} value={p.slug}>{p.display_name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">From Date</label>
            <input type="date" className="input" value={filters.recon_date || filters.date_from}
              onChange={e => setFilters({...filters, recon_date: '', date_from: e.target.value})} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">To Date</label>
            <input type="date" className="input" value={filters.recon_date || filters.date_to}
              onChange={e => setFilters({...filters, recon_date: '', date_to: e.target.value})} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Side</label>
            <select className="select" value={filters.side} onChange={e => setFilters({...filters, side: e.target.value})}>
              <option value="">Both</option>
              <option value="bank">Bank</option>
              <option value="internal">Internal</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Aging</label>
            <select className="select" value={filters.aging} onChange={e => setFilters({...filters, aging: e.target.value})}>
              <option value="">All</option>
              <option value="d1">D+1 (yesterday)</option>
              <option value="d3">D+3 (2–3 days)</option>
              <option value="d7">D+7+ (4+ days)</option>
            </select>
          </div>
          <div className={fieldApplies('src_code', filters.partner) ? '' : 'opacity-40 pointer-events-none'}
               title={fieldApplies('src_code', filters.partner) ? '' : 'SRC codes apply to core-ledger products only'}>
            <label className="text-xs text-gray-400 block mb-1">SRC Code</label>
            <select className="select" value={filters.src_code} disabled={!fieldApplies('src_code', filters.partner)}
                    onChange={e => setFilters({...filters, src_code: e.target.value})}>
              <option value="">All</option>
              {SRC_CODES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Bank A/c</label>
            <select className="select" value={filters.bank_account}
                    onChange={e => setFilters({...filters, bank_account: e.target.value})}>
              <option value="">All accounts</option>
              {bankAccounts
                .filter(a => !filters.partner || a.partner === filters.partner)
                .map(a => <option key={a.id} value={a.account_number}>{a.label || a.account_number}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Eko TID</label>
            <input className="input" placeholder="A,B,C or partial" value={filters.eko_tid}
              title="Single TID or comma-separated list: A,B,C"
              onChange={e => setFilters({...filters, eko_tid: e.target.value})} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Tracking No</label>
            <input className="input" placeholder="A,B,C or partial" value={filters.tracking_number}
              title="Single tracking number or comma-separated list: A,B,C"
              onChange={e => setFilters({...filters, tracking_number: e.target.value})} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Recon ID</label>
            <input className="input" placeholder="FNO-..." value={filters.match_id}
              onChange={e => setFilters({...filters, match_id: e.target.value})} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Amount Min</label>
            <input type="number" className="input" placeholder="0" value={filters.amount_min}
              onChange={e => setFilters({...filters, amount_min: e.target.value})} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Amount Max</label>
            <input type="number" className="input" placeholder="∞" value={filters.amount_max}
              onChange={e => setFilters({...filters, amount_max: e.target.value})} />
          </div>
        </div>
        <div className="flex gap-2 mt-3">
          <button onClick={() => load(1)} className="btn-primary flex items-center gap-1.5"><Search size={14} /> Search</button>
          <button onClick={() => setFilters({ partner: '', recon_date: '', date_from: '', date_to: '', side: '', src_code: '', eko_tid: '', tracking_number: '', match_id: '', recon_status: '', aging: '', amount_min: '', amount_max: '', bank_account: '' })} className="btn-ghost">Clear</button>
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="table-th w-8">
                  <input type="checkbox"
                    checked={items.length > 0 && selected.size === items.length}
                    onChange={toggleAll} className="cursor-pointer" />
                </th>
                <th className="table-th">Partner</th>
                <th className="table-th">Bank A/c</th>
                <th className="table-th">Side</th>
                <th className="table-th">Date</th>
                <th className="table-th">Age</th>
                <th className="table-th">Eko TID</th>
                <th className="table-th">Tracking No</th>
                <th className="table-th">UTR No</th>
                <th className="table-th text-right">Amount</th>
                <th className="table-th">DR/CR</th>
                <th className="table-th">Recon Status</th>
                <th className="table-th">Recon ID</th>
                <th className="table-th">SRC</th>
                <th className="table-th">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={COLS} className="text-center py-10 text-gray-400 text-sm">Loading...</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={COLS} className="text-center py-10 text-gray-400 text-sm">No transactions found</td></tr>
              ) : (
                items.map(item => (
                  <tr key={item.id}
                    className={`hover:bg-gray-50 border-b border-gray-50 ${selected.has(item.id) ? 'bg-primary/5' : ''}`}>
                    <td className="table-td">
                      <input type="checkbox" checked={selected.has(item.id)} onChange={() => toggleRow(item.id)} className="cursor-pointer" />
                    </td>
                    <td className="table-td capitalize font-medium">{item.partner}</td>
                    <td className="table-td font-mono text-xs text-gray-500">{item.bank_account ? `…${String(item.bank_account).slice(-4)}` : '—'}</td>
                    <td className="table-td"><span className={`capitalize ${item.side === 'bank' ? 'badge-blue' : 'badge-gray'}`}>{item.side}</span></td>
                    <td className="table-td font-mono text-xs">{item.recon_date}</td>
                    <td className="table-td">
                      {item.aging_bucket && AGING_BADGE[item.aging_bucket]
                        ? <span className={`text-xs px-1.5 py-0.5 rounded ${AGING_BADGE[item.aging_bucket].cls}`}>
                            {AGING_BADGE[item.aging_bucket].label}
                          </span>
                        : '—'}
                    </td>
                    <td className="table-td font-mono text-xs">{item.eko_tid || '—'}</td>
                    <td className="table-td font-mono text-xs">{item.tracking_number || '—'}</td>
                    <td className="table-td font-mono text-xs">{item.utr_number || '—'}</td>
                    <td className="table-td text-right tabular-nums font-medium">
                      {item.amount != null
                        ? <span className={item.dr_cr === 'CR' ? 'text-green-600' : item.dr_cr === 'DR' ? 'text-gray-800' : 'text-gray-600'}>
                            {item.amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </span>
                        : '—'}
                    </td>
                    <td className="table-td">
                      {item.dr_cr
                        ? <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${item.dr_cr === 'DR' ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-600'}`}>
                            {item.dr_cr}
                          </span>
                        : '—'}
                    </td>
                    <td className="table-td">
                      <span className={`capitalize ${STATUS_BADGE[item.recon_status] || 'badge-gray'}`}>
                        {item.recon_status === 'amount_mismatch' ? '⚠ Amt Mismatch'
                          : item.recon_status === 'duplicate'    ? '⊗ Duplicate'
                          : item.recon_status === 'failed'       ? '✕ Failed'
                          : (item.recon_status || '').replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="table-td">
                      {item.match_id
                        ? <span
                            className="font-mono text-xs text-primary cursor-pointer hover:underline"
                            title="Click to filter by this Recon ID"
                            onClick={() => setFilters(f => ({...f, match_id: item.match_id, recon_status: 'all'}))}
                          >{item.match_id}</span>
                        : '—'}
                    </td>
                    <td className="table-td">
                      {item.src_code ? <span className="badge-yellow">{item.src_code}</span> : '—'}
                    </td>
                    <td className="table-td">
                      <div className="flex flex-col gap-1">
                        {(item.recon_status === 'unmatched' || item.recon_status === 'amount_mismatch') && (
                          <button
                            onClick={() => { setSrcModal(item); setSrcForm({ src_code: item.src_code || '', src_note: item.src_note || '' }) }}
                            className="text-xs text-primary hover:underline flex items-center gap-1"
                          >
                            <Tag size={12} /> Assign SRC
                          </button>
                        )}
                        {item.side === 'bank' && item.recon_status === 'unmatched' && (
                          <button
                            onClick={() => { setAdhocModal(item); setAdhocRemark('') }}
                            className="text-xs text-orange-600 hover:underline flex items-center gap-1"
                          >
                            <Banknote size={12} /> Tag Adhoc
                          </button>
                        )}
                        {/* Manual interbank match — for fund_transfer rows (override perm required) */}
                        {hasOverride && item.recon_status === 'fund_transfer' && (
                          interbankSelect?.id === item.id
                            ? <button
                                onClick={() => setInterbankSelect(null)}
                                className="text-xs text-indigo-600 font-semibold hover:underline flex items-center gap-1 bg-indigo-50 px-1.5 py-0.5 rounded"
                              >
                                <ArrowLeftRight size={12} /> Selected ✕
                              </button>
                            : interbankSelect
                              ? <button
                                  onClick={() => setInterbankModal({ txnA: interbankSelect, txnB: item })}
                                  className="text-xs text-indigo-700 font-semibold hover:underline flex items-center gap-1 bg-indigo-100 px-1.5 py-0.5 rounded animate-pulse"
                                >
                                  <ArrowLeftRight size={12} /> Pair with A
                                </button>
                              : <button
                                  onClick={() => setInterbankSelect(item)}
                                  className="text-xs text-indigo-500 hover:underline flex items-center gap-1"
                                >
                                  <ArrowLeftRight size={12} /> Select (A)
                                </button>
                        )}
                        {/* Override buttons — only visible to users with override permission */}
                        {hasOverride && item.match_id && ['matched','manual_matched','interbank_matched'].includes(item.recon_status) && (
                          <button
                            onClick={() => setOverrideModal({ action: 'unmatch', match_id: item.match_id, item })}
                            className="text-xs text-red-500 hover:underline flex items-center gap-1"
                            title="Break this match — both transactions returned to unmatched"
                          >
                            ✕ Unmatch
                          </button>
                        )}
                        {hasOverride && !['matched','manual_matched','interbank_matched'].includes(item.recon_status) && (
                          <button
                            onClick={() => setOverrideModal({ action: 'override', item, newStatus: 'unmatched' })}
                            className="text-xs text-gray-400 hover:text-red-500 hover:underline flex items-center gap-1"
                            title="Override this transaction's status (requires remark)"
                          >
                            ⚙ Override
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > 50 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 text-sm">
            <span className="text-gray-500">Showing {((page-1)*50)+1}–{Math.min(page*50, total)} of {total.toLocaleString()}</span>
            <div className="flex gap-2">
              <button onClick={() => load(page-1)} disabled={page === 1} className="btn-ghost px-3 py-1 text-xs disabled:opacity-40">Prev</button>
              <button onClick={() => load(page+1)} disabled={page*50 >= total} className="btn-ghost px-3 py-1 text-xs disabled:opacity-40">Next</button>
            </div>
          </div>
        )}
      </div>

      {/* Single SRC Modal */}
      {srcModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-800">Assign Special Reason Code</h3>
              <button onClick={() => setSrcModal(null)} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
            </div>
            <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-600 mb-4 space-y-1">
              <div><span className="font-medium">Eko TID:</span> {srcModal.eko_tid || '—'}</div>
              <div><span className="font-medium">Tracking:</span> {srcModal.tracking_number || '—'}</div>
              <div><span className="font-medium">Amount:</span> {srcModal.amount?.toLocaleString() || '—'}</div>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-gray-500 block mb-1">SRC Code</label>
                <select className="select" value={srcForm.src_code} onChange={e => setSrcForm({...srcForm, src_code: e.target.value})}>
                  <option value="">Select code</option>
                  {SRC_CODES.map(c => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 block mb-1">Note (optional)</label>
                <textarea className="input" rows={2} placeholder="Add a note..."
                  value={srcForm.src_note} onChange={e => setSrcForm({...srcForm, src_note: e.target.value})} />
              </div>
            </div>
            <div className="flex gap-3 mt-4">
              <button onClick={() => setSrcModal(null)} className="btn-ghost flex-1">Cancel</button>
              <button onClick={handleAssignSrc} className="btn-primary flex-1">Assign SRC</button>
            </div>
          </div>
        </div>
      )}

      {/* Adhoc Settlement Modal */}
      {adhocModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-800 flex items-center gap-2">
                <Banknote size={16} className="text-orange-500" />
                Tag as Adhoc Settlement
              </h3>
              <button onClick={() => setAdhocModal(null)} className="text-gray-400 hover:text-gray-600"><X size={18}/></button>
            </div>

            {/* Transaction info */}
            <div className="bg-orange-50 border border-orange-100 rounded-lg p-3 text-xs text-orange-800 mb-4 space-y-1">
              <p className="font-semibold mb-1">Adhoc Settlement — bank-side debit with no Simplibank record</p>
              <div><span className="font-medium">Partner:</span> {adhocModal.partner} · <span className="font-medium">Date:</span> {adhocModal.recon_date}</div>
              <div><span className="font-medium">Amount:</span> ₹{Number(adhocModal.amount || 0).toLocaleString('en-IN')}</div>
              {adhocModal.eko_tid && <div><span className="font-medium">Eko TID:</span> {adhocModal.eko_tid}</div>}
            </div>

            {/* Mandatory remark */}
            <div className="mb-4">
              <label className="text-xs font-semibold text-gray-700 block mb-1">
                Remark <span className="text-red-500">*</span>
                <span className="text-gray-400 font-normal ml-1">(required — cannot save without a remark)</span>
              </label>
              <textarea
                className="input"
                rows={3}
                placeholder="Explain why this is an adhoc settlement to CSP/SCSP — this remark is permanently recorded in the audit trail."
                value={adhocRemark}
                onChange={e => setAdhocRemark(e.target.value)}
                autoFocus
              />
              {!adhocRemark.trim() && (
                <p className="text-xs text-red-500 mt-1">Remark is mandatory. Entry will not be saved without it.</p>
              )}
            </div>

            <div className="flex gap-3">
              <button onClick={() => setAdhocModal(null)} className="btn-ghost flex-1">Cancel</button>
              <button
                onClick={handleTagAdhoc}
                disabled={adhocSaving || !adhocRemark.trim()}
                className="btn-primary flex-1"
                style={{ background: '#f97316' }}
              >
                {adhocSaving ? 'Saving…' : 'Tag as Adhoc Settlement'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Override Modal */}
      {bulkOverrideOpen && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-800 flex items-center gap-2">
                <ShieldAlert size={16} className="text-red-500" />
                Bulk Override — {selected.size} transaction(s)
              </h3>
              <button onClick={() => setBulkOverrideOpen(false)} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
            </div>
            <div className="bg-red-50 border border-red-100 rounded-lg p-3 text-xs text-red-800 mb-4">
              This will change the status of <strong>{selected.size}</strong> transaction(s). Any existing matches will be broken. This is permanently recorded in the audit trail as a human action.
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-gray-700 block mb-1">New Status</label>
                <select className="select" value={bulkOverrideForm.new_status}
                  onChange={e => setBulkOverrideForm(f => ({ ...f, new_status: e.target.value }))}>
                  <option value="unmatched">Unmatched</option>
                  <option value="failed">Failed</option>
                  <option value="src_assigned">SRC Assigned</option>
                  <option value="adhoc_settlement">Adhoc Settlement</option>
                  <option value="human_override">Human Override</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-semibold text-gray-700 block mb-1">
                  Remark <span className="text-red-500">*</span>
                  <span className="text-gray-400 font-normal ml-1">(mandatory — applies to all {selected.size} entries)</span>
                </label>
                <textarea className="input" rows={3}
                  placeholder="Explain why all selected transactions are being overridden…"
                  value={bulkOverrideForm.remark}
                  onChange={e => setBulkOverrideForm(f => ({ ...f, remark: e.target.value }))}
                  autoFocus />
                {!bulkOverrideForm.remark.trim() && (
                  <p className="text-xs text-red-500 mt-1">Remark is mandatory. Will not save without it.</p>
                )}
              </div>
            </div>
            <div className="flex gap-3 mt-4">
              <button onClick={() => setBulkOverrideOpen(false)} className="btn-ghost flex-1">Cancel</button>
              <button
                onClick={handleBulkOverride}
                disabled={bulkOverrideSaving || !bulkOverrideForm.remark.trim()}
                className="btn-danger flex-1"
              >
                {bulkOverrideSaving ? 'Saving…' : `Override ${selected.size} Transactions`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Interbank Select Banner — shown when first txn is selected, prompting user to pick the second */}
      {interbankSelect && !interbankModal && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 bg-indigo-600 text-white rounded-xl shadow-xl px-5 py-3 flex items-center gap-4 text-sm">
          <ArrowLeftRight size={16} />
          <span>
            <span className="font-semibold">Transaction A selected</span>
            {' '}— {interbankSelect.partner} · {interbankSelect.recon_date} · ₹{Number(interbankSelect.amount||0).toLocaleString('en-IN')}
            {interbankSelect.utr_number && <span className="ml-1 opacity-75">UTR: {interbankSelect.utr_number}</span>}
          </span>
          <span className="opacity-75 text-xs">Now click "Pair with A" on the matching transaction</span>
          <button onClick={() => setInterbankSelect(null)} className="ml-2 opacity-75 hover:opacity-100">✕</button>
        </div>
      )}

      {/* Manual Interbank Match Confirmation Modal */}
      {interbankModal && (
        <RemarkModal
          title="Manual Interbank Match"
          subtitle={
            `Pair these two fund-transfer entries as an interbank match (IBT- ID):\n` +
            `A: ${interbankModal.txnA.partner} · ${interbankModal.txnA.recon_date} · ₹${Number(interbankModal.txnA.amount||0).toLocaleString('en-IN')}${interbankModal.txnA.utr_number ? ' · UTR: '+interbankModal.txnA.utr_number : ''}\n` +
            `B: ${interbankModal.txnB.partner} · ${interbankModal.txnB.recon_date} · ₹${Number(interbankModal.txnB.amount||0).toLocaleString('en-IN')}${interbankModal.txnB.utr_number ? ' · UTR: '+interbankModal.txnB.utr_number : ''}`
          }
          placeholder="Explain why this interbank match is being done manually — permanently recorded in audit trail."
          onConfirm={async (remark) => {
            await api.post('/recon/manual-interbank-match', {
              txn_id_a: interbankModal.txnA.id,
              txn_id_b: interbankModal.txnB.id,
              remark,
            })
            toast.success('Interbank match created')
            setInterbankModal(null)
            setInterbankSelect(null)
            load(page)
          }}
          onClose={() => { setInterbankModal(null); setInterbankSelect(null) }}
        />
      )}

      {/* Override / Unmatch Modal — for users with override permission */}
      {overrideModal && (
        <RemarkModal
          title={overrideModal.action === 'unmatch'
            ? `Break Match — ${overrideModal.match_id}`
            : `Override Status — ${overrideModal.item?.eko_tid || overrideModal.item?.id}`
          }
          subtitle={overrideModal.action === 'unmatch'
            ? 'Both transactions in this match will be set back to Unmatched.'
            : `Current status: ${overrideModal.item?.recon_status} → New: ${overrideModal.newStatus}`
          }
          placeholder="Explain why this override is needed — permanently recorded in audit trail as a human action."
          onConfirm={async (remark) => {
            try {
              if (overrideModal.action === 'unmatch') {
                await api.post('/recon/unmatch', { match_id: overrideModal.match_id, remark })
                toast.success(`Match ${overrideModal.match_id} broken`)
              } else {
                await api.post('/recon/override-status', {
                  transaction_id: overrideModal.item.id,
                  new_status: overrideModal.newStatus,
                  remark,
                })
                toast.success('Status overridden')
              }
              setOverrideModal(null)
              load(page)
            } catch (err) {
              toast.error(err.response?.data?.detail || 'Override failed')
              throw err  // keep modal open so user can correct
            }
          }}
          onClose={() => setOverrideModal(null)}
        />
      )}
    </div>
  )
}

// ── Reusable Remark Modal ─────────────────────────────────────────────────────
// Used by any action that requires a mandatory remark (override, adhoc, etc.)
export function RemarkModal({ title, subtitle, placeholder, onConfirm, onClose }) {
  const [remark, setRemark] = useState('')
  const [saving, setSaving] = useState(false)

  const handleConfirm = async () => {
    if (!remark.trim()) return toast.error('Remark is required — entry cannot be saved without it')
    setSaving(true)
    try {
      await onConfirm(remark.trim())
    } catch {
      // error handling done by caller
    } finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-gray-800 text-sm">{title}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={16}/></button>
        </div>
        {subtitle && (
          <p className="text-xs text-gray-500 bg-gray-50 rounded-lg px-3 py-2 mb-4">{subtitle}</p>
        )}
        <div className="mb-4">
          <label className="text-xs font-semibold text-gray-700 block mb-1">
            Remark <span className="text-red-500">*</span>
            <span className="text-gray-400 font-normal ml-1">(mandatory)</span>
          </label>
          <textarea className="input" rows={3} placeholder={placeholder}
            value={remark} onChange={e => setRemark(e.target.value)} autoFocus />
          {!remark.trim() && (
            <p className="text-xs text-red-500 mt-1">Cannot save without a remark.</p>
          )}
        </div>
        <div className="flex gap-3">
          <button onClick={onClose} className="btn-ghost flex-1">Cancel</button>
          <button onClick={handleConfirm} disabled={saving || !remark.trim()} className="btn-primary flex-1">
            {saving ? 'Saving…' : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  )
}