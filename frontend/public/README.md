# Brand assets (not in git)

The Eko logo is a **trademark**, not MIT-licensed code, so the real artwork is deliberately
**not committed** to this repository. `frontend/public/eko-logo.*` is gitignored.

## Running your own deployment

Drop your organisation's logo here as:

```
frontend/public/eko-logo.png
```

It is rendered **as supplied** — no redraw, recolour, crop or filter. Notes:

- A **wordmark** (wider than tall) works best: callers set a `height` and the width follows the
  artwork's own aspect ratio, so it is never distorted.
- Use a transparent background (RGBA). The sidebar renders it on the dark petrol-teal
  (`#094053`), the login page on white.
- Supply it at roughly 2× the largest rendered size (the login header is 44 px tall) so it stays
  crisp on high-DPI screens.
- Vite copies everything in `public/` to the **root** of `dist/`, not into `assets/`. When
  deploying by hand, upload `dist/eko-logo.png` to the web root alongside `index.html` — it is a
  separate file from the hashed bundle, and forgetting it is the classic 404.

**If the file is absent** — a fresh clone, or a fork with its own branding — the UI falls back to
a plain text wordmark. That fallback is intentionally generic; it is a placeholder, not a
reproduction of the registered mark, and should not be made to resemble one.

To rebrand, replace this one file. No code changes are needed.
