# Yandex Direct Audit (MVP)

Monorepo: FastAPI backend + Next.js frontend + Docker Compose for local development.

**Hosting note:** this repo does not modify system nginx. On a shared host, add a dedicated `server` or `location` for this app only — see `infra/nginx/README.shared-hosting.md`.

## Quick start (Docker)

```bash
cp env.example .env
docker compose up --build
```

- API: http://localhost:8000/api/v1/docs  
- Health: http://localhost:8000/api/v1/health  
- Web: http://localhost:3000  

Postgres is exposed on **5433**, Redis on **6380** (to avoid clashing with other local projects).

## Local backend without Docker

```bash
cd apps/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://audit:audit@localhost:5433/audit
uvicorn app.main:app --reload --port 8000
```

## Local frontend without Docker

```bash
cd apps/frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Roadmap: 13 этапов в ТЗ; завершён **Этап 1 — Bootstrap**.
