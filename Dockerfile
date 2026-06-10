# ── Stage 1: build the React frontend ───────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python backend (serves the built frontend from /frontend/dist) ─
FROM python:3.11-slim
WORKDIR /app/backend

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
# main.py serves ../frontend/dist when it exists
COPY --from=frontend /build/dist /app/frontend/dist

# Uploaded statements + SQLite data dir — mount volumes in production
RUN mkdir -p uploads data
VOLUME ["/app/backend/uploads", "/app/backend/data"]

# Default the SQLite file onto the data volume so it survives container
# recreation. Real env vars (compose env_file / -e) override this, and the
# app's dotenv loader never overrides real env vars.
ENV DATABASE_URL=sqlite:////app/backend/data/recon.db

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
