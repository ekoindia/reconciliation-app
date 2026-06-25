import React, { useState, useEffect, useCallback } from 'react'
import { Bookmark, Save, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import api from '../utils/api'

/**
 * Saved Views control (roadmap 1.3). Lists the user's own + shared views for a
 * page, applies a view's stored filter dict via onApply, and lets the user save
 * the current filters. Read/replay only — never changes list-query semantics.
 *
 * Props: page (string), filters (object), onApply(query) => void
 */
export default function SavedViews({ page, filters, onApply }) {
  const [views, setViews]     = useState([])
  const [selected, setSelected] = useState('')
  const [saving, setSaving]   = useState(false)
  const [showSave, setShowSave] = useState(false)
  const [name, setName]       = useState('')
  const [shared, setShared]   = useState(false)

  const load = useCallback(() => {
    api.get('/views', { params: { page } }).then(r => setViews(r.data.views || [])).catch(() => {})
  }, [page])
  useEffect(() => { load() }, [load])

  const apply = (id) => {
    setSelected(id)
    const v = views.find(x => x.id === id)
    if (v) onApply(v.query || {})
  }

  const save = async () => {
    if (!name.trim()) { toast.error('Name required'); return }
    setSaving(true)
    try {
      const active = Object.fromEntries(Object.entries(filters).filter(([, v]) => v))
      await api.post('/views', { name: name.trim(), page, query: active, is_shared: shared })
      toast.success('View saved')
      setShowSave(false); setName(''); setShared(false); load()
    } catch { toast.error('Save failed') }
    finally { setSaving(false) }
  }

  const remove = async (id, e) => {
    e.stopPropagation()
    if (!confirm('Delete this saved view?')) return
    try {
      await api.delete(`/views/${id}`)
      toast.success('Deleted'); if (selected === id) setSelected(''); load()
    } catch { toast.error('Delete failed') }
  }

  const ownsSelected = selected && views.find(v => v.id === selected)?.owned

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <div className="flex items-center gap-1.5">
        <Bookmark size={14} className="text-primary" />
        <select className="select py-1 text-xs min-w-[150px]" value={selected} onChange={e => apply(e.target.value)}>
          <option value="">Saved views…</option>
          {views.map(v => (
            <option key={v.id} value={v.id}>
              {v.name}{v.is_shared ? ' (shared)' : ''}{!v.owned ? ` · ${v.username}` : ''}
            </option>
          ))}
        </select>
      </div>
      {ownsSelected && (
        <button onClick={(e) => remove(selected, e)} className="btn-ghost px-2 py-1 text-xs text-red-600" title="Delete view">
          <Trash2 size={13} />
        </button>
      )}
      {!showSave ? (
        <button onClick={() => setShowSave(true)} className="btn-ghost px-2 py-1 text-xs flex items-center gap-1">
          <Save size={13} /> Save current
        </button>
      ) : (
        <div className="flex items-center gap-1.5">
          <input autoFocus className="input py-1 text-xs w-40" placeholder="View name" value={name}
            onChange={e => setName(e.target.value)} onKeyDown={e => e.key === 'Enter' && save()} />
          <label className="text-xs flex items-center gap-1 text-gray-500">
            <input type="checkbox" checked={shared} onChange={e => setShared(e.target.checked)} /> share
          </label>
          <button onClick={save} disabled={saving} className="btn-primary px-2 py-1 text-xs">Save</button>
          <button onClick={() => { setShowSave(false); setName('') }} className="btn-ghost px-2 py-1 text-xs">Cancel</button>
        </div>
      )}
    </div>
  )
}
