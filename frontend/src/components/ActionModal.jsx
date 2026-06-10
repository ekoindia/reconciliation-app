import React, { useState, useEffect } from 'react'

// Branded replacement for window.prompt/confirm on financial actions (audit F2).
//
// config = {
//   title, description, confirmLabel, danger,
//   fields: [{ name, label, type: 'select'|'text', options, placeholder,
//              required, minLength, default }],
// }
// onSubmit(values) is called with { fieldName: value } after validation.
export default function ActionModal({ open, config, onSubmit, onClose, busy = false }) {
  const [values, setValues] = useState({})
  const [err, setErr] = useState('')

  useEffect(() => {
    if (open && config) {
      const init = {}
      ;(config.fields || []).forEach(f => {
        init[f.name] = f.default ?? (f.type === 'select'
          ? (typeof f.options?.[0] === 'string' ? f.options?.[0] : f.options?.[0]?.value) ?? ''
          : '')
      })
      setValues(init); setErr('')
    }
  }, [open, config])

  if (!open || !config) return null

  const submit = () => {
    for (const f of (config.fields || [])) {
      const v = (values[f.name] ?? '').toString().trim()
      if (f.required && !v) { setErr(`${f.label} is required`); return }
      if (f.minLength && v.length < f.minLength) { setErr(`${f.label} must be at least ${f.minLength} characters`); return }
    }
    onSubmit(values)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-5" onClick={e => e.stopPropagation()}>
        <h3 className="font-bold text-gray-800 mb-1">{config.title}</h3>
        {config.description && <p className="text-xs text-gray-500 mb-4">{config.description}</p>}
        <div className="space-y-3">
          {(config.fields || []).map(f => (
            <div key={f.name}>
              <label className="block text-xs text-gray-500 mb-1">{f.label}{f.required ? ' *' : ''}</label>
              {f.type === 'select' ? (
                <select className="select w-full" value={values[f.name] ?? ''}
                  onChange={e => setValues(v => ({ ...v, [f.name]: e.target.value }))}>
                  {(f.options || []).map(o => typeof o === 'string'
                    ? <option key={o} value={o}>{o}</option>
                    : <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              ) : (
                <input className="input w-full" placeholder={f.placeholder || ''} value={values[f.name] ?? ''}
                  onChange={e => setValues(v => ({ ...v, [f.name]: e.target.value }))}
                  onKeyDown={e => { if (e.key === 'Enter') submit() }} />
              )}
            </div>
          ))}
        </div>
        {err && <p className="text-xs text-red-500 mt-3">{err}</p>}
        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose} disabled={busy} className="btn-ghost text-sm">Cancel</button>
          <button onClick={submit} disabled={busy}
            className={`text-sm px-4 py-2 rounded-lg font-medium text-white transition-opacity disabled:opacity-50 ${config.danger ? 'bg-red-600 hover:bg-red-700' : 'bg-primary hover:opacity-90'}`}>
            {busy ? 'Working…' : (config.confirmLabel || 'Confirm')}
          </button>
        </div>
      </div>
    </div>
  )
}
