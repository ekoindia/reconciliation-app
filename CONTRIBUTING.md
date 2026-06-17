# Contributing to Eko Recon

Thanks for your interest in improving Eko Recon! This document explains how to get a
development environment running and what we expect from contributions.

## Development setup

### Prerequisites

| Tool    | Version |
|---------|---------|
| Python  | 3.10+   |
| Node.js | 18+     |
| npm     | 9+      |

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # then edit values — see comments inside
uvicorn main:app --reload --port 8000
```

The app runs on SQLite out of the box (`backend/recon.db` is created automatically).
No external database is required for development.

### Frontend

```bash
cd frontend
npm install
npm run dev                # http://localhost:3000, proxies /api → :8000
```

### Tests

```bash
cd backend
pytest tests/ -q
```

## Pull request guidelines

1. **One concern per PR.** Small, reviewable changes merge fastest.
2. **Never change reconciliation behavior silently.** Matching rules, ingestion
   mappings, amount/date parsing, and status transitions are load-bearing for
   financial accuracy. If your change affects how transactions match, say so
   prominently in the PR description and include before/after examples.
3. **No real data in the repo.** Never commit bank statements, transaction dumps,
   `.env` files, or database files — the `.gitignore` blocks these for a reason.
   Use synthetic fixtures for tests.
4. **Match the existing style.** Backend: FastAPI routes in `backend/routes/`,
   shared logic in `backend/core/`, models in `backend/models/database.py`.
   Frontend: pages in `frontend/src/pages/`, shared UI in `frontend/src/components/`,
   shared classes in `frontend/src/index.css`.
5. **Run the verification suite before pushing:**
   ```bash
   cd backend && pytest tests/ -q
   cd frontend && npm run build
   ```

## Branching model

- `main` — stable, released code.
- `dev` — integration branch for the next release; branch features off `dev` and open PRs against it.
- `feature/<name>` — new features (branch from `dev`).
- `bugfix/<name>` — non-urgent fixes (branch from `dev`).
- `hotfix/<name>` — urgent fixes to a release (branch from `main`, merged back into both).

## Commit messages

Lowercase, present-tense, imperative, and prefixed by type — e.g.
`feat: add bank-statement narration`. Common prefixes: `feat`, `fix`, `docs`, `style`,
`refactor`, `test`, `chore`, `ci`, `security`, `config`.

## Reporting bugs

Open a GitHub issue with:
- What you did (steps, file formats involved)
- What you expected vs. what happened
- Relevant log output (scrub any real transaction data first!)

## Security issues

Please do **not** open public issues for vulnerabilities — see [SECURITY.md](SECURITY.md).
