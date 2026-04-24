import type { Metadata } from "next";
import Link from "next/link";
import { SiteHelpLink } from "@/components/site-help-link";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Handoff | Модуль аудита Яндекс Директ",
  description: "Внутренняя справка по YaDirect-analytics для команды и ИИ",
  robots: { index: false, follow: false },
};

export default function HandoffPage() {
  return (
    <main className="mx-auto max-w-3xl space-y-10 px-4 py-10 text-sm leading-relaxed md:px-6">
      <header className="space-y-3 border-b pb-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Handoff</h1>
            <p className="text-sm text-muted-foreground">Внутренний контекст проекта и правила эксплуатации.</p>
          </div>
          <div className="flex items-center gap-2">
            <SiteHelpLink />
            <Button variant="secondary" asChild>
              <Link href="/handoff">Handoff</Link>
            </Button>
            <Button variant="secondary" asChild>
              <Link href="/rules">Правила</Link>
            </Button>
            <Button variant="secondary" asChild>
              <Link href="/settings">Настройки</Link>
            </Button>
            <Button variant="secondary" asChild>
              <Link href="/dashboard">Главная</Link>
            </Button>
          </div>
        </div>
        <p className="text-muted-foreground">
          Кратко по сути (ориентир — «легенда» уровней L1/L2/L3 в{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">temp/легенда.txt</code>
          ), архитектура, окружение, Docker/nginx, выкладка и единый каталог правил.
        </p>
        <p className="text-muted-foreground">
          Пользовательская справка по проверкам:{" "}
          <Link href="/help" className="text-primary underline-offset-4 hover:underline">
            /help
          </Link>
          .
        </p>
      </header>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Суть проекта</h2>
        <p>
          Внутренний сервис аудита рекламных кампаний <strong>Яндекс Директ</strong> с уровнями проверок{" "}
          <strong>L1 / L2 / L3</strong> и слоем <strong>AI-assisted</strong> (Polza.ai). Цели: автоматизировать
          проверки, хранить историю находок, корректно считать статусы{" "}
          <code className="rounded bg-muted px-1">new / existing / fixed / reopened</code>, выявлять признаки
          саботажа, выдавать рекомендации и показывать результаты в веб-интерфейсе.
        </p>
        <p className="text-muted-foreground">
          Текущая рабочая конфигурация на проде: deterministic-проверки активны; отдельные AI-assisted правила в активном
          каталоге могут отсутствовать. При этом AI-этап изолирован и не должен менять lifecycle deterministic-находок.
        </p>
        <ul className="list-inside list-disc space-y-1 text-muted-foreground">
          <li>
            <strong>L1</strong> — только данные рекламного кабинета.
          </li>
          <li>
            <strong>L2</strong> — кабинет и статистика.
          </li>
          <li>
            <strong>L3</strong> — кабинет и техническая HTTP-проверка ссылок.
          </li>
        </ul>
        <p className="text-muted-foreground">
          Градация критичности (из той же «легенды»): предупреждение → высокий приоритет → критично (влияние на
          трафик, бюджет, показы).
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Архитектура</h2>
        <ul className="list-inside list-disc space-y-1 text-muted-foreground">
          <li>
            <strong>Монорепо</strong>: backend (FastAPI) + frontend (Next.js) в одном репозитории.
          </li>
          <li>
            <strong>Backend</strong>: FastAPI, SQLAlchemy (async), Alembic, Celery, Redis, PostgreSQL. Аудиты L1/L2/L3,
            отдельный AI-сервис, lifecycle находок, задачи в воркере.
          </li>
          <li>
            <strong>Frontend</strong>: Next.js, TypeScript, дашборд аккаунтов/кампаний/находок, настройки, справка.
          </li>
          <li>
            <strong>Интеграции</strong>: API Яндекс Директ, OAuth Яндекса для привязки кабинета, Polza.ai для AI-этапа.
          </li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Окружение и сервисы (Docker Compose)</h2>
        <p className="text-muted-foreground">
          В корне репозитория файл <code className="rounded bg-muted px-1">docker-compose.yml</code> поднимает:
          <strong> db</strong> (Postgres), <strong>redis</strong>, <strong>backend</strong> (uvicorn),{" "}
          <strong>worker</strong> и <strong>beat</strong> (Celery), <strong>frontend</strong> (Next). Переменные
          окружения задаются через <code className="rounded bg-muted px-1">.env</code> в корне (см.{" "}
          <code className="rounded bg-muted px-1">env.example</code>). Pydantic подхватывает переменные из окружения
          процесса (как задаёт Compose) и при локальной разработке — <code className="rounded bg-muted px-1">.env</code>{" "}
          рядом с <code className="rounded bg-muted px-1">docker-compose.yml</code>.
        </p>
        <p className="text-muted-foreground">
          <strong>Сборка backend / worker / beat</strong> идёт с <strong>контекстом всего монорепо</strong> (
          <code className="rounded bg-muted px-1">build.context: .</code>,{" "}
          <code className="rounded bg-muted px-1">dockerfile: apps/backend/Dockerfile</code>): в образ копируется код{" "}
          <code className="rounded bg-muted px-1">apps/backend/</code> и для согласованности с UI — снимок{" "}
          <code className="rounded bg-muted px-1">apps/frontend/src/data/rule-catalog.json</code> →{" "}
          <code className="rounded bg-muted px-1">/app/frontend-data/rule-catalog.json</code> (тесты выравнивания
          каталога). В корне репозитория есть <code className="rounded bg-muted px-1">.dockerignore</code> (исключает{" "}
          <code className="rounded bg-muted px-1">node_modules</code>, <code className="rounded bg-muted px-1">.next</code>,{" "}
          <code className="rounded bg-muted px-1">temp</code> и т.д. из контекста сборки).
        </p>
        <p className="text-muted-foreground">
          Порты на <strong>хосте</strong> по умолчанию: backend <code className="rounded bg-muted px-1">8010→8000</code>, frontend{" "}
          <code className="rounded bg-muted px-1">3001→3000</code>. Общий nginx должен проксировать на{" "}
          <strong>8010</strong> (API) и <strong>3001</strong> (Next), иначе будет <strong>502</strong>. Актуальный пример:{" "}
          <code className="rounded bg-muted px-1">infra/nginx/atorichko.asur-adigital.ru-locations.conf.example</code>.
        </p>
        <p className="text-muted-foreground">
          На VDS за обратным прокси часто стоит <strong>общий nginx</strong> с другими проектами: этот стек{" "}
          <strong>не</strong> ставит nginx сам — проксируется только на порты контейнеров (см.{" "}
          <code className="rounded bg-muted px-1">infra/nginx/README.shared-hosting.md</code>
          ).
        </p>
        <p className="text-muted-foreground">
          Публичный путь деплоя (пример): префикс{" "}
          <code className="rounded bg-muted px-1">/YaDirect-analytics/</code>, API —{" "}
          <code className="rounded bg-muted px-1">.../api/v1</code>. В <code className="rounded bg-muted px-1">.env</code>{" "}
          должны совпадать <code className="rounded bg-muted px-1">NEXT_PUBLIC_BASE_PATH</code> и{" "}
          <code className="rounded bg-muted px-1">NEXT_PUBLIC_API_V1_URL</code> с реальным URL. Для отладки OAuth:{" "}
          <code className="rounded bg-muted px-1">GET /api/v1/health</code> возвращает поле{" "}
          <code className="rounded bg-muted px-1">yandex_oauth_redirect_uri</code> — то, что реально видит процесс backend.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Репозиторий</h2>
        <p className="text-muted-foreground">
          GitHub: <strong>atorichko/YaDirect-analytics</strong>. Типичный путь на сервере разработки/CI:{" "}
          <code className="rounded bg-muted px-1">/root/YaDirect-analytics</code> (на VDS путь может отличаться —
          ориентируйтесь на каталог, где лежат <code className="rounded bg-muted px-1">docker-compose.yml</code> и{" "}
          <code className="rounded bg-muted px-1">.env</code>).
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Логика выкладки на продакшн</h2>
        <ol className="list-inside list-decimal space-y-2 text-muted-foreground">
          <li>
            <strong>Сначала git</strong>: изменения коммитятся и пушатся в основную ветку (например{" "}
            <code className="rounded bg-muted px-1">main</code>).
          </li>
          <li>
            <strong>Потом VDS</strong>: на сервере <code className="rounded bg-muted px-1">git pull</code> в каталоге
            проекта.
          </li>
          <li>
            <strong>Сборка и миграции</strong>: пересборка образов, при необходимости{" "}
            <code className="rounded bg-muted px-1">alembic upgrade head</code>, перезапуск контейнеров.
          </li>
          <li>
            <strong>Nginx</strong>: правки только своего <code className="rounded bg-muted px-1">location</code> /
            файла сайта; <code className="rounded bg-muted px-1">nginx -t</code> и <code className="rounded bg-muted px-1">reload</code>, не ломая чужие проекты.
          </li>
        </ol>
        <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-amber-950 dark:text-amber-100">
          <strong>Важно (заказчик):</strong> на сервере крутятся и другие проекты — при смене конфигурации nginx или
          общих ресурсов не трогать чужие блоки. Выкладка: <strong>сначала git, потом VDS</strong>. Команды в терминале по
          возможности выполняет ассистент/автоматизация, иначе — вручную по чеклисту ниже.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Каталог правил аудита</h2>
        <ul className="list-inside list-disc space-y-2 text-muted-foreground">
          <li>
            <strong>Единственный файл каталога в git</strong> для UI и для загрузки в API:{" "}
            <code className="rounded bg-muted px-1">apps/frontend/src/data/rule-catalog.json</code>. Отдельные копии
            в корне, в{" "}
            <code className="rounded bg-muted px-1">temp/</code> или в{" "}
            <code className="rounded bg-muted px-1">tests/fixtures/</code> <strong>не используются</strong> — удалены,
            чтобы не расходились с фронтом.
          </li>
          <li>
            Страница <Link href="/help" className="text-primary underline-offset-4 hover:underline">/help</Link> и
            бэкенд-тесты выравнивания опираются на тот же JSON (в Docker — копия из образа, см. выше).
          </li>
          <li>
            Реализация проверок в коде: <code className="rounded bg-muted px-1">l1_rules.py</code>,{" "}
            <code className="rounded bg-muted px-1">l2_rules.py</code>, <code className="rounded bg-muted px-1">l3_rules.py</code> и сервисы аудитов в{" "}
            <code className="rounded bg-muted px-1">apps/backend/app/services/</code>.
          </li>
          <li>
            В <strong>продакшене</strong> аудиты опираются на <strong>активную версию каталога в БД</strong>, а не только
            на JSON в репозитории. Загрузка и активация через API (админ):{" "}
            <code className="rounded bg-muted px-1">POST /api/v1/rule-catalogs</code> и{" "}
            <code className="rounded bg-muted px-1">POST /api/v1/rule-catalogs/{"{id}"}/activate</code>. Текущий активный:{" "}
            <code className="rounded bg-muted px-1">GET /api/v1/rule-catalogs/active</code>. Тело запроса загрузки —
            содержимое <code className="rounded bg-muted px-1">rule-catalog.json</code>.
          </li>
          <li>
            Поле <code className="rounded bg-muted px-1">check_type</code> хранится в БД в{" "}
            <code className="rounded bg-muted px-1">rule_definitions</code> (см.{" "}
            <code className="rounded bg-muted px-1">apps/backend/app/models/rule_catalog.py</code>) и отдается API
            каталогов. В git-файле <code className="rounded bg-muted px-1">apps/frontend/src/data/rule-catalog.json</code>{" "}
            поле <code className="rounded bg-muted px-1">check_type</code> сейчас отсутствует, поэтому источник истины
            для него - только активный каталог в БД.
          </li>
        </ul>
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
          <strong>Обязательно:</strong> после изменений каталога правил на проде нужно{" "}
          <strong>заново загрузить каталог и активировать</strong> его. Иначе новые проверки в коде/JSON{" "}
          <strong>не начнут применяться</strong> в соответствии с обновлённым каталогом в БД.
        </p>

        <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
          <h3 className="text-base font-semibold text-foreground">Как обновить каталог на проде (API, админ)</h3>
          <p className="text-muted-foreground">
            Публичный префикс API на этом стенде:{" "}
            <code className="rounded bg-muted px-1 break-all">
              https://atorichko.asur-adigital.ru/YaDirect-analytics/api/v1
            </code>
            . OpenAPI:{" "}
            <a
              href="https://atorichko.asur-adigital.ru/YaDirect-analytics/api/v1/docs"
              className="text-primary underline-offset-4 hover:underline break-all"
              target="_blank"
              rel="noreferrer"
            >
              …/api/v1/docs
            </a>
            . Эндпоинты:{" "}
            <code className="rounded bg-muted px-1">POST /rule-catalogs</code> (загрузка) и{" "}
            <code className="rounded bg-muted px-1">POST /rule-catalogs/{"{id}"}/activate</code> (активация). Текущий
            активный каталог: <code className="rounded bg-muted px-1">GET /rule-catalogs/active</code>.
          </p>
          <p className="text-muted-foreground">
            Тело <code className="rounded bg-muted px-1">POST /rule-catalogs</code> в коде — схема{" "}
            <code className="rounded bg-muted px-1">CatalogUploadRequest</code> (поля{" "}
            <code className="rounded bg-muted px-1">rule_name</code>,{" "}
            <code className="rounded bg-muted px-1">check_type</code> и т.д.). Файл в git —{" "}
            <code className="rounded bg-muted px-1">rule-catalog.json</code> в другом виде (
            <code className="rounded bg-muted px-1">name_ru</code> и пр.). Чтобы не собирать JSON вручную, используйте
            скрипт из репозитория:{" "}
            <code className="rounded bg-muted px-1">apps/backend/scripts/upload_rule_catalog_api.py</code> — он читает{" "}
            <code className="rounded bg-muted px-1">apps/frontend/src/data/rule-catalog.json</code>, маппит правила в
            формат API и выставляет <code className="rounded bg-muted px-1">check_type</code> (deterministic / ai_assisted)
            по реестрам L1/L2/L3.
          </p>
          <p className="font-medium text-foreground">Порядок действий (с VDS или любой машины с доступом в git и HTTPS до прода)</p>
          <ol className="list-inside list-decimal space-y-2 text-muted-foreground">
            <li>
              Получить access-токен админа: <code className="rounded bg-muted px-1">POST …/auth/login</code> с телом{" "}
              <code className="rounded bg-muted px-1">{"{ \"email\", \"password\" }"}</code>. Учётные данные того же
              bootstrap-админа задаются в корневом <code className="rounded bg-muted px-1">.env</code>:{" "}
              <code className="rounded bg-muted px-1">SEED_ADMIN_EMAIL</code>,{" "}
              <code className="rounded bg-muted px-1">SEED_ADMIN_PASSWORD</code> (см.{" "}
              <code className="rounded bg-muted px-1">scripts/seed_admin.py</code>). Пароль в документацию и в чат не
              копировать.
            </li>
            <li>
              В каталоге <code className="rounded bg-muted px-1">apps/backend</code> выставить переменные и запустить
              скрипт:
              <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded bg-background p-3 font-mono text-[0.75rem] leading-normal md:text-[0.8rem]">
                {`export API_BASE_URL="https://atorichko.asur-adigital.ru/YaDirect-analytics/api/v1"
export ADMIN_ACCESS_TOKEN="<access_token из ответа login>"
python3 scripts/upload_rule_catalog_api.py`}
              </pre>
            </li>
            <li>
              Если ответ загрузки <strong>409</strong> и текст вроде «Catalog version already exists for platform» —
              версия <code className="rounded bg-muted px-1">catalog_version</code> уже занята в БД. Повторить с новой
              версией (семвер выше текущей активной, смотреть в{" "}
              <code className="rounded bg-muted px-1">GET /rule-catalogs/active</code>):
              <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded bg-background p-3 font-mono text-[0.75rem] leading-normal md:text-[0.8rem]">
                {`python3 scripts/upload_rule_catalog_api.py --catalog-version 1.0.2`}
              </pre>
              Скрипт сам вызовет <code className="rounded bg-muted px-1">activate</code> для загруженного id.
            </li>
            <li>
              Проверка без записи в БД:{" "}
              <code className="rounded bg-muted px-1">python3 scripts/upload_rule_catalog_api.py --dry-run</code> (печать
              JSON тела).
            </li>
            <li>
              После успешной заливки имеет смысл обновить в git поле{" "}
              <code className="rounded bg-muted px-1">catalog_version</code> в{" "}
              <code className="rounded bg-muted px-1">apps/frontend/src/data/rule-catalog.json</code> на ту же строку,
              что ушла на прод — чтобы локальный файл и БД не расходились по номеру версии.
            </li>
          </ol>
        </div>
        <p className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-emerald-950 dark:text-emerald-100">
          <strong>Актуальные нюансы lifecycle:</strong> deterministic-проверки (L1/L2/L3) имеют приоритет над AI. AI
          не может закрыть ошибку, если по тому же <code className="rounded bg-muted px-1">rule_code + entity_key</code>{" "}
          есть открытая deterministic-находка. Если в активном каталоге нет правил{" "}
          <code className="rounded bg-muted px-1">check_type=ai_assisted</code>, AI-этап не меняет статусы.
        </p>
        <p className="text-muted-foreground">
          Для карточек правил в БД добавлены поля <code className="rounded bg-muted px-1">rule_description</code> и{" "}
          <code className="rounded bg-muted px-1">fix_recommendation</code> (таблица{" "}
          <code className="rounded bg-muted px-1">rule_definitions</code>). Страница{" "}
          <Link href="/rules" className="text-primary underline-offset-4 hover:underline">
            /rules
          </Link>{" "}
          выводит эти значения как источник описания и рекомендации.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Порядок обновления продакшн (команды)</h2>
        <p className="text-muted-foreground">
          Выполняйте на <strong>VDS</strong> в каталоге репозитория (где <code className="rounded bg-muted px-1">docker-compose.yml</code>
          ). Подставьте свой путь, если не <code className="rounded bg-muted px-1">/root/YaDirect-analytics</code>.
        </p>

        <div className="space-y-4 rounded-lg border bg-muted/30 p-4 font-mono text-xs md:text-sm">
          <div>
            <p className="mb-2 font-sans text-sm font-medium text-foreground">1. Git: закоммитить локально и отправить</p>
            <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-background p-3 text-[0.8rem] leading-normal">
{`cd /root/YaDirect-analytics
git status
git add -A
git commit -m "описание изменений"
git push origin main`}
            </pre>
          </div>
          <div>
            <p className="mb-2 font-sans text-sm font-medium text-foreground">2. На VDS: получить код</p>
            <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-background p-3 text-[0.8rem] leading-normal">
{`cd /root/YaDirect-analytics
git fetch origin
git checkout main
git pull --ff-only origin main`}
            </pre>
          </div>
          <div>
            <p className="mb-2 font-sans text-sm font-medium text-foreground">
              3. Сборка образов и миграции БД
            </p>
            <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-background p-3 text-[0.8rem] leading-normal">
{`# backend/worker/beat собираются из корня репозитория (нужен доступ к frontend rule-catalog.json)
docker compose build backend worker beat frontend
docker compose run --rm backend alembic upgrade head`}
            </pre>
          </div>
          <div>
            <p className="mb-2 font-sans text-sm font-medium text-foreground">4. Запуск / перезапуск стека</p>
            <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-background p-3 text-[0.8rem] leading-normal">
{`docker compose up -d db redis backend worker beat frontend
docker compose ps`}
            </pre>
            <p className="mt-2 font-sans text-xs text-muted-foreground">
              При смене только backend-логики без фронта можно не пересобирать frontend; при смене env — пересоздайте
              контейнеры:{" "}
              <code className="rounded bg-muted px-1">
                docker compose up -d --force-recreate backend worker beat
              </code>
              .
            </p>
          </div>
          <div>
            <p className="mb-2 font-sans text-sm font-medium text-foreground">5. Общий nginx (не трогать чужие проекты)</p>
            <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-background p-3 text-[0.8rem] leading-normal">
{`sudo nginx -t && sudo systemctl reload nginx`}
            </pre>
          </div>
          <div>
            <p className="mb-2 font-sans text-sm font-medium text-foreground">6. Дымовые проверки</p>
            <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-background p-3 text-[0.8rem] leading-normal">
{`curl -fsS https://atorichko.asur-adigital.ru/YaDirect-analytics/api/v1/health
# при необходимости проверить redirect_uri для OAuth:
# в ответе /health поле yandex_oauth_redirect_uri`}
            </pre>
          </div>
          <div>
            <p className="mb-2 font-sans text-sm font-medium text-foreground">7. Каталог правил после обновления кода</p>
            <p className="mb-2 font-sans text-xs text-muted-foreground">
              Подробный сценарий (URL прода, login, скрипт, 409 и версия) — в разделе{" "}
              <strong>«Как обновить каталог на проде (API, админ)»</strong> выше на этой странице.
            </p>
            <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-background p-3 text-[0.8rem] leading-normal">
{`cd /root/YaDirect-analytics/apps/backend
export API_BASE_URL="https://atorichko.asur-adigital.ru/YaDirect-analytics/api/v1"
export ADMIN_ACCESS_TOKEN="<после POST .../auth/login>"
python3 scripts/upload_rule_catalog_api.py
# при 409: python3 scripts/upload_rule_catalog_api.py --catalog-version <новая>`}
            </pre>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Расширенный чеклист: <code className="rounded bg-muted px-1">RELEASE_CHECKLIST.md</code> в корне репозитория.
        </p>
      </section>
    </main>
  );
}
