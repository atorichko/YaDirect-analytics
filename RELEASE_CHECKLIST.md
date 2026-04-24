# Release Checklist (VDS)

## 0) Pre-flight

- [ ] Confirm current branch and clean working tree.
- [ ] Verify `.env` for production values:
  - [ ] `ENVIRONMENT=production`
  - [ ] strong `JWT_SECRET_KEY` (>= 32 chars)
  - [ ] `POLZA_AI_API_KEY` set
  - [ ] `NEXT_PUBLIC_BASE_PATH=/YaDirect-analytics`
  - [ ] `NEXT_PUBLIC_API_V1_URL=https://atorichko.asur-adigital.ru/YaDirect-analytics/api/v1`
- [ ] Verify DB backups policy before migration.

## 1) Build and migrations

- [ ] Pull latest code on VDS.
- [ ] Build images (backend/worker/beat use monorepo root context — подтягивают `rule-catalog.json` из frontend):
  - `docker compose build backend worker beat frontend`
- [ ] Run migrations:
  - `docker compose run --rm backend alembic upgrade head`
- [ ] Seed admin (idempotent):
  - `docker compose run --rm backend python scripts/seed_admin.py`

## 2) Start services

- [ ] Start stack:
  - `docker compose up -d db redis backend worker frontend`
- [ ] (If used) start beat scheduler:
  - `docker compose up -d beat`
- [ ] Confirm containers healthy:
  - `docker compose ps`

## 3) Shared nginx path deploy safety

- [ ] Update only dedicated `location /YaDirect-analytics/` block.
- [ ] Do NOT modify unrelated project locations.
- [ ] Reload nginx:
  - `sudo nginx -t && sudo systemctl reload nginx`

## 4) Functional smoke checks

- [ ] `GET /api/v1/health` returns 200.
- [ ] Login as admin works.
- [ ] Dashboard opens at:
  - `https://atorichko.asur-adigital.ru/YaDirect-analytics/`
- [ ] `POST /audits/l1/run-job` returns `task_id`.
- [ ] `GET /audits/jobs/{task_id}` reaches `SUCCESS`.
- [ ] Findings visible in dashboard table.

## 5) Post-release monitoring

- [ ] Check worker logs for task errors.
- [ ] Check backend logs for 5xx.
- [ ] Check audit job throughput for first scheduled cycle.
- [ ] Confirm no regressions in other nginx-hosted projects.

## 6) Rollback (minimal)

- [ ] Keep previous working image tags.
- [ ] If severe issue:
  - [ ] rollback image tag
  - [ ] restart affected services
  - [ ] restore DB from backup if migration-related issue
