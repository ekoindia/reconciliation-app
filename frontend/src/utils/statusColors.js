// Shared recon-status → Tailwind badge classes — single source of truth (audit F9/F11).
// Matched family = green, processed/assigned = blue/teal, problems = amber/red.

export const STATUS_COLOR = {
  matched:           'bg-green-50 text-green-700',
  manual_matched:    'bg-green-50 text-green-700',
  matched_online:    'bg-green-50 text-green-700',
  matched_cash:      'bg-emerald-50 text-emerald-700',
  matched_manual:    'bg-teal-50 text-teal-700',
  interbank_matched: 'bg-emerald-50 text-emerald-700',
  internal_matched:  'bg-emerald-50 text-emerald-700',
  fee_matched:       'bg-emerald-50 text-emerald-700',
  reversal_matched:  'bg-emerald-50 text-emerald-700',
  failed_refunded:   'bg-emerald-50 text-emerald-700',
  adhoc_settlement:  'bg-teal-50 text-teal-700',
  src_assigned:      'bg-blue-50 text-blue-700',
  amount_mismatch:   'bg-amber-50 text-amber-700',
  wrong_amount:      'bg-amber-50 text-amber-700',
  twice_credit:      'bg-orange-50 text-orange-700',
  human_override:    'bg-purple-50 text-purple-700',
  under_review:      'bg-yellow-50 text-yellow-700',
  written_off:       'bg-gray-200 text-gray-600',
  failed:            'bg-gray-100 text-gray-600',
  failed_pending_refund: 'bg-red-50 text-red-600',
  refunded_but_success:  'bg-orange-50 text-orange-700',
  unmatched:         'bg-red-50 text-red-600',
  unmatched_bank:    'bg-red-50 text-red-600',
  unmatched_internal:'bg-red-50 text-red-600',
  unmatched_load:    'bg-red-50 text-red-600',
}

export const statusColor = (s) => STATUS_COLOR[s] || 'bg-gray-100 text-gray-600'
