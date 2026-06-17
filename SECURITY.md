# Security Policy

Eko Recon processes financial transaction data, so we take security reports seriously.

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report privately through the GitHub Security Advisory — go to the **"Security"** tab
and choose **"Report a Vulnerability"**
([direct link](https://github.com/ekoindia/reconciliation-app/security/advisories/new)).
You can also email **app.support@eko.co.in**.

Please include:
- A description of the vulnerability and its impact
- Steps to reproduce
- Any suggested remediation

The team will acknowledge your report and keep you informed of progress toward a fix.

## Scope

Of particular interest:
- Authentication/authorization bypass (JWT or API-key handling)
- SQL injection or unsafe file handling in the upload/ingestion pipeline
- Path traversal via uploaded file names or watch-folder configuration
- Privilege escalation between user roles

## Deployment hardening checklist

If you operate an Eko Recon instance:
- Set a strong, unique `SECRET_KEY` in `backend/.env` (the app refuses to mint
  trustworthy sessions without one)
- Change the default admin password immediately after first login
- Set `ALLOWED_ORIGINS` to your real frontend origin — never `*`
- Run behind TLS (reverse proxy such as nginx/Caddy)
- Keep `uploads/` and the database on encrypted storage; both contain raw
  transaction data
- Install `slowapi` so rate limiting is active (enabled automatically when present)
