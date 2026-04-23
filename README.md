# YaDirect Analytics (MVP)

Monorepo: FastAPI + Next.js + Docker Compose. Репозиторий: [YaDirect-analytics](https://github.com/atorichko/YaDirect-analytics).

**Общий nginx на VDS:** правьте только свой фрагмент `location`, не трогайте чужие проекты. См. `infra/nginx/README.shared-hosting.md` и `infra/nginx/atorichko.asur-adigital.ru-locations.conf.example`.

Публичный URL (path deploy): `https://atorichko.asur-adigital.ru/YaDirect-analytics/` — в `.env` на сервере задайте `NEXT_PUBLIC_BASE_PATH=/YaDirect-analytics` и `NEXT_PUBLIC_API_V1_URL=https://atorichko.asur-adigital.ru/YaDirect-analytics/api/v1`.

## Quick start (Docker)

```bash
cd /root/YaDirect-analytics   # или ваш путь к клону
cp env.example .env
docker compose up --build -d db redis
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python scripts/seed_admin.py
docker compose up backend worker frontend
```

- API docs: http://localhost:8000/api/v1/docs  
- Health: http://localhost:8000/api/v1/health  
- Web: http://localhost:3000  

Postgres **5433**, Redis **6380** (снаружи), чтобы не пересекаться с другими сервисами.

## Этапы

1. Bootstrap — готово.  
2. Auth + RBAC — JWT, `admin` / `specialist`, `GET /users/me`, `GET /users` (admin), страницы `/login` и `/dashboard`.

## Тесты (backend)

```bash
cd apps/backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```
