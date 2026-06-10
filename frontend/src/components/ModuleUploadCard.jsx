import React, { useState, useRef } from 'react'
import { FileText, X } from 'lucide-react'

// Visual twin of the core-product upload card (GenericProductCards in Upload.jsx):
// colored icon box · title + description · date note · dashed drop-zone that holds
// the selected file · an "Upload …" button. Use for dedicated modules (E-Value,
// BBPS, …) so every product's upload looks identical.
//
// Props:
//   icon, title, desc      — header
//   color                  — 'blue' | 'cyan' | 'green' | 'purple' | 'orange' | 'amber'
//   accept                 — file input accept string
//   onUpload(file)         — called with the chosen File when the button is clicked
//   busy                   — disables + shows "Parsing…"
//   disabled               — fully disabled (e.g. account not yet picked)
//   dateNote               — small note shown where core cards show the date control
//   buttonLabel            — overrides "Upload {title} →"
//   children               — extra controls rendered above the drop-zone (e.g. selectors)

const COLORS = {
  blue:   { box: 'bg-blue-100',   btn: '#2563eb', hover: 'hover:border-blue-400'   },
  cyan:   { box: 'bg-cyan-100',   btn: '#0891b2', hover: 'hover:border-cyan-400'   },
  green:  { box: 'bg-green-100',  btn: '#16a34a', hover: 'hover:border-green-400'  },
  purple: { box: 'bg-purple-100', btn: '#9333ea', hover: 'hover:border-purple-400' },
  orange: { box: 'bg-orange-100', btn: '#f97316', hover: 'hover:border-orange-400' },
  amber:  { box: 'bg-amber-100',  btn: '#d97706', hover: 'hover:border-amber-400'  },
}

export default function ModuleUploadCard({
  icon, title, desc, color = 'blue', accept = '.csv,.xlsx,.xls',
  onUpload, busy = false, disabled = false,
  dateNote = 'Date auto-detected from each row', buttonLabel, children,
}) {
  const [file, setFile] = useState(null)
  const ref = useRef()
  const c = COLORS[color] || COLORS.blue

  return (
    <div className="rounded-xl border-2 border-gray-200 bg-white p-5 transition-all hover:border-gray-300">
      <div className="flex items-center gap-2.5 mb-4">
        <div className={`p-2 ${c.box} rounded-lg text-xl`}>{icon}</div>
        <div>
          <h2 className="font-bold text-gray-800">{title}</h2>
          <p className="text-xs text-gray-400">{desc}</p>
        </div>
      </div>
      <div className="space-y-3">
        {children}
        {dateNote && (
          <p className="text-xs rounded-lg px-3 py-2 bg-gray-50 border border-gray-100 text-gray-500">{dateNote}</p>
        )}
        <div
          onClick={() => { if (!disabled) ref.current && ref.current.click() }}
          className={`border-2 border-dashed border-gray-200 rounded-xl p-5 text-center cursor-pointer ${c.hover} transition-colors ${disabled ? 'opacity-50 pointer-events-none' : ''}`}>
          {file
            ? <div className="flex items-center justify-center gap-2 text-gray-600">
                <FileText size={16} /><span className="text-sm font-medium truncate max-w-xs">{file.name}</span>
                <button onClick={e => { e.stopPropagation(); setFile(null) }} className="text-gray-400 hover:text-red-500"><X size={13} /></button>
              </div>
            : <div className="text-gray-400"><FileText size={20} className="mx-auto mb-1.5" /><p className="text-xs">Click to select file</p><p className="text-xs text-gray-300 mt-0.5">Excel · CSV</p></div>}
          <input ref={ref} type="file" accept={accept} hidden
            onChange={e => { const f = e.target.files?.[0]; if (f) setFile(f); e.target.value = '' }} />
        </div>
        <button
          onClick={() => { if (file) { onUpload(file); setFile(null) } }}
          disabled={!file || busy || disabled}
          className="btn-primary w-full"
          style={{ background: file && !disabled ? c.btn : undefined }}>
          {busy ? 'Parsing…' : (buttonLabel || `Upload ${title} →`)}
        </button>
      </div>
    </div>
  )
}
