// Shared money/date formatters — single source of truth.
// Use these instead of redefining per page (audit finding F9).

/** Full INR with 2 decimals: ₹1,23,456.00 */
export const inr = (n) =>
  '₹' + Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })

/** Compact INR in lakh/crore for dashboards: ₹54.20L / ₹1.2Cr */
export const fmtINRCompact = (n) => {
  const v = Number(n || 0)
  const abs = Math.abs(v)
  if (abs >= 1e7) return '₹' + (v / 1e7).toFixed(2) + 'Cr'
  if (abs >= 1e5) return '₹' + (v / 1e5).toFixed(2) + 'L'
  return '₹' + v.toLocaleString('en-IN', { maximumFractionDigits: 0 })
}

/** Today's date as YYYY-MM-DD */
export const today = () => new Date().toISOString().split('T')[0]
