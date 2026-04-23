# Commit Plan (Stage Grouping)

Recommended non-interactive commit sequence:

1. `chore(bootstrap): scaffold monorepo and local infra`
   - stage 1 baseline files, docker, env, frontend/backend skeleton.

2. `feat(auth): add JWT auth and RBAC for admin/specialist`
   - stage 2 auth routes, guards, models, seed admin.

3. `feat(core): add audit domain entities and migrations`
   - stage 3 account/snapshot/audit/finding/exceptions/action logs.

4. `feat(rule-catalog): add catalog import, versioning, activation`
   - stage 4 models/repositories/services/routes for catalog.

5. `feat(integration): add yandex direct sync abstractions`
   - stage 5 adapters, sync pipeline, raw/normalized snapshots.

6. `feat(engine-l1): implement deterministic L1 checks`
   - stage 6 rule registry + L1 audit service + tests.

7. `feat(engine-l2): implement deterministic L2 checks`
   - stage 7 statistics/strategy/budget checks + tests.

8. `feat(engine-l3): implement deterministic L3 URL checks`
   - stage 8 URL/redirect/SSL/UTM checks + tests.

9. `feat(ai): integrate Polza.ai with validated JSON verdicts`
   - stage 9 AI client, schema validation, ai_interactions storage.

10. `feat(history): add finding lifecycle and sabotage detection`
    - stage 10 new/existing/fixed/reopened logic + tests.

11. `feat(scheduler): add weekly jobs and task status endpoints`
    - stage 11 celery beat schedule, run-job, task status API.

12. `feat(frontend): add MVP dashboard for audits and findings`
    - stage 12 frontend pages/components + reporting endpoints.

13. `docs(polish): add runbook, release checklist and demo seed`
    - stage 13 tests/docs/seed polish.
