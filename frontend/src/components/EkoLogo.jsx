// ─────────────────────────────────────────────────────────────────────────────
// Brand mark.
//
// The real Eko logo is a TRADEMARK and is deliberately NOT committed to this
// public repo. Deployments drop the official file at `frontend/public/eko-logo.png`
// (gitignored — see frontend/public/README.md); it is then rendered untouched: no
// redraw, recolour, crop or filter. Replacing that one file is the whole rebrand.
//
// When the file is absent (a fresh clone, or a fork with its own branding) the
// <img> 404s and we fall back to a plain text wordmark — deliberately generic, so
// nobody mistakes a stand-in for the registered mark. Do NOT "improve" that
// fallback into a lookalike of the real logo.
//
// The asset is a wordmark (wider than tall), so callers set `height` and the width
// follows the artwork's own aspect ratio. src is BASE_URL-prefixed because
// production is served under the /recon/ subpath.
// ─────────────────────────────────────────────────────────────────────────────
import { useState } from 'react'

const SRC = `${import.meta.env.BASE_URL}eko-logo.png`
const BRAND = '#F9AB10'

export default function EkoLogo({ height = 40, className = '', alt = 'Eko' }) {
  const [missing, setMissing] = useState(false)

  if (missing) {
    // Neutral placeholder — NOT a reproduction of the registered logo.
    return (
      <span
        className={`inline-flex items-center font-extrabold leading-none select-none ${className}`}
        style={{ height, fontSize: height * 0.62, color: BRAND, letterSpacing: '-0.03em' }}
        aria-label={alt}
      >
        eko
      </span>
    )
  }

  return (
    <img
      src={SRC}
      alt={alt}
      onError={() => setMissing(true)}
      // height drives the box; width auto-follows so the logo is never distorted
      style={{ height, width: 'auto' }}
      className={`block select-none ${className}`}
      draggable="false"
    />
  )
}
