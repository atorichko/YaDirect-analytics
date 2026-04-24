import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Контекст проекта (handoff)",
  description: "Внутренняя справка по YaDirect-analytics для команды и ИИ",
  robots: { index: false, follow: false },
};

export default function HandoffPage() {
  return (
    <main className="mx-auto max-w-3xl space-y-10 px-4 py-10 text-sm leading-relaxed md:px-6">
      <header className="space-y-2 border-b pb-6">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Скрытая страница — только по прямой ссылке
        </p>
        <h1 className="text-2xl font-semibold tracking-tight">YaDirect-analytics — контекст для работы</h1>
        <p className="text-muted-foreground">
          Кратко по сути (ориентир — ТЗ и «легенда» уровней в{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">temp/легенда.txt</code>
          ), архитектура, окружение, выкладка и каталог правил.
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
          <code className="rounded bg-muted px-1">env.example</code>).
        </p>
        <p className="text-muted-foreground">
          На VDS за обратным прокси часто стоит <strong>общий nginx</strong> с другими проектами: этот стек{" "}
          <strong>не</strong> ставит nginx сам — проксируется только на порты контейнеров (см.{" "}
          <code className="rounded bg-muted px-1">infra/nginx/README.shared-hosting.md</code>
          ).
        </p>
        <p className="text-muted-foreground">
          Публичный путь деплоя (пример из README): префикс{" "}
          <code className="rounded bg-muted px-1">/YaDirect-analytics/</code>, API —{" "}
          <code className="rounded bg-muted px-1">.../api/v1</code>. В <code className="rounded bg-muted px-1">.env</code>{" "}
          должны совпадать <code className="rounded bg-muted px-1">NEXT_PUBLIC_BASE_PATH</code> и{" "}
          <code className="rounded bg-muted px-1">NEXT_PUBLIC_API_V1_URL</code> с реальным URL.
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
            Исходники описаний и справки во фронте: например{" "}
            <code className="rounded bg-muted px-1">apps/frontend/src/data/rule-catalog.json</code>, корневой{" "}
            <code className="rounded bg-muted px-1">каталог правил.json</code> (и копии в{" "}
            <code className="rounded bg-muted px-1">temp/</code> для черновиков).
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
            <code className="rounded bg-muted px-1">GET /api/v1/rule-catalogs/active</code>.
          </li>
        </ul>
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
          <strong>Обязательно:</strong> после изменений каталога правил на проде нужно{" "}
          <strong>заново загрузить каталог и активировать</strong> его. Иначе новые проверки в коде/JSON{" "}
          <strong>не начнут применяться</strong> в соответствии с обновлённым каталогом в БД.
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
{`docker compose build backend worker beat frontend
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
            <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-background p-3 text-[0.8rem] leading-normal">
{`# Через API под админом: загрузить JSON каталога, затем activate.
# См. POST /api/v1/rule-catalogs и POST .../activate в OpenAPI:
# /YaDirect-analytics/api/v1/docs`}
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
