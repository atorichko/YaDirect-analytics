# YaDirect Analytics (MVP)

Внутренний сервис аудита рекламных кампаний Яндекс Директ для performance-команды.

Монорепо:
- backend: FastAPI + SQLAlchemy + Alembic + Celery + Redis + PostgreSQL
- frontend: Next.js + TypeScript + TanStack Table + shadcn/ui

Репозиторий: [YaDirect-analytics](https://github.com/atorichko/YaDirect-analytics)

## Реализованные этапы

- Этапы `1–13` MVP закрыты:
  - bootstrap монорепо
  - auth + RBAC (`admin`/`specialist`)
  - core entities + migrations
  - импорт и активация rule catalog
  - L1/L2/L3 deterministic engine
  - Polza.ai AI-assisted layer
  - lifecycle findings (`new/existing/fixed/reopened`) + `suspected_sabotage`
  - manual/weekly jobs + task status
  - dashboard UI (accounts/campaigns/findings + run buttons)

## Локальный запуск (Docker)

0) Создать `.env` из шаблона:

```bash
cp env.example .env
```

1) Поднять инфраструктуру и приложение:

```bash
cd /root/YaDirect-analytics
docker compose up --build -d
```

2) Применить миграции:

```bash
docker compose run --rm backend alembic upgrade head
```

3) Засидить админа:

```bash
docker compose run --rm backend python scripts/seed_admin.py
```

4) (Опционально) Засидить демо-данные для UI/аудитов:

```bash
docker compose run --rm backend python scripts/seed_demo_data.py
```

5) Доступ:
- backend docs: `http://localhost:8010/api/v1/docs`
- frontend: `http://localhost:3001`

## Основные API

- Auth:
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/refresh`
- Users:
  - `GET /api/v1/users/me`
  - `GET /api/v1/users` (admin)
- Rule catalogs:
  - `POST /api/v1/rule-catalogs`
  - `POST /api/v1/rule-catalogs/{catalog_id}/activate`
  - `GET /api/v1/rule-catalogs/active`
- Reporting:
  - `GET /api/v1/ad-accounts`
  - `GET /api/v1/ad-accounts/{account_id}/campaigns`
  - `GET /api/v1/findings?account_id=<uuid>&limit=200`
- Audits:
  - sync run: `POST /api/v1/audits/l1|l2|l3|ai/run`
  - async run: `POST /api/v1/audits/l1|l2|l3|ai/run-job`
  - weekly jobs: `POST /api/v1/audits/weekly/sync/run-job`, `POST /api/v1/audits/weekly/audit/run-job`
  - job status: `GET /api/v1/audits/jobs/{task_id}`

## Переменные окружения (ключевые)

- DB/Redis/Celery:
  - `DATABASE_URL`, `DATABASE_URL_SYNC`
  - `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- Security:
  - `JWT_SECRET_KEY`, `JWT_ACCESS_EXPIRE_MINUTES`, `JWT_REFRESH_EXPIRE_DAYS`
- AI:
  - `POLZA_AI_BASE_URL`, `POLZA_AI_API_KEY`, `AI_MODEL`
- Policies:
  - `MIN_CONVERSIONS_FOR_LEARNING`
  - `MAX_REDIRECT_HOPS`
  - `SABOTAGE_REOPEN_WINDOW_DAYS`
- Scheduler:
  - `WEEKLY_CRON_MINUTE`
  - `WEEKLY_CRON_HOUR`
  - `WEEKLY_CRON_DAY_OF_WEEK`

## Тесты

Backend:

```bash
docker compose run --rm backend pytest -q
```

Frontend build smoke:

```bash
cd apps/frontend
npm install
npm run build
```

## Shared nginx / path deploy

Публичный URL: `https://atorichko.asur-adigital.ru/YaDirect-analytics/`

**502 Bad Gateway:** nginx не достучался до upstream. По умолчанию в `docker-compose.yml` backend слушает на хосте **`127.0.0.1:8010`**, frontend — **`127.0.0.1:3001`**. В `proxy_pass` должны быть эти порты (или те, что вы задали сами). См. актуальный пример: `infra/nginx/atorichko.asur-adigital.ru-locations.conf.example`.

В server env:
- `NEXT_PUBLIC_BASE_PATH=/YaDirect-analytics`
- `NEXT_PUBLIC_API_V1_URL=https://atorichko.asur-adigital.ru/YaDirect-analytics/api/v1`

Важно: при shared nginx править только свой `location`-блок.
См. `infra/nginx/README.shared-hosting.md`.
