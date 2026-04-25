"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AppSectionNav } from "@/components/app-section-nav";
import { PublishBundledCatalogBlock } from "@/components/publish-bundled-catalog-block";
import { getAccessToken } from "@/lib/auth";
import { apiGet } from "@/lib/api-client";

type Me = { role: "admin" | "specialist" };

type RuleDefinition = {
  rule_code: string;
  rule_name: string;
  rule_description: string | null;
  fix_recommendation: string | null;
  level: "L1" | "L2" | "L3";
  check_type: "deterministic" | "ai_assisted";
  enabled: boolean;
  config: Record<string, unknown>;
};

type ActiveCatalog = {
  version: string;
  updated_at?: string;
  rules: RuleDefinition[];
};

type CoverageSnapshot = {
  catalog_version: string;
  catalog_updated_at?: string;
  ai_appendix_rule_codes?: string[];
};

function ruleDescription(rule: RuleDefinition): string {
  if (rule.rule_description && rule.rule_description.trim()) {
    return rule.rule_description.trim();
  }
  const cfg = rule.config ?? {};
  const candidates = [
    cfg.description_ru,
    cfg.description,
    cfg.detection_logic,
    cfg.fail_condition,
    cfg.recommendation_ru,
  ];
  for (const item of candidates) {
    if (typeof item === "string" && item.trim()) {
      return item.trim();
    }
  }
  return "Описание не заполнено в каталоге.";
}

function ruleRecommendation(rule: RuleDefinition): string {
  if (rule.fix_recommendation && rule.fix_recommendation.trim()) {
    return rule.fix_recommendation.trim();
  }
  const cfg = rule.config ?? {};
  const value = cfg.recommendation_ru;
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }
  return "Рекомендация не заполнена в каталоге.";
}

const POLL_MS = 12_000;

export default function RulesPage() {
  const [error, setError] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<ActiveCatalog | null>(null);
  const [coverageMeta, setCoverageMeta] = useState<CoverageSnapshot | null>(null);
  const [adminOk, setAdminOk] = useState(false);
  const [autoRefreshNote, setAutoRefreshNote] = useState<string | null>(null);
  const token = useMemo(() => getAccessToken(), []);
  const catalogFingerprintRef = useRef<string | null>(null);

  const loadCatalog = useCallback(async (activeToken: string) => {
    const data = await apiGet<ActiveCatalog>("/rule-catalogs/active", activeToken);
    setCatalog(data);
  }, []);

  const refreshCoverageMeta = useCallback(async (activeToken: string) => {
    const cov = await apiGet<CoverageSnapshot>("/rule-catalogs/active/coverage", activeToken);
    setCoverageMeta(cov);
    return cov;
  }, []);

  useEffect(() => {
    if (!catalog) return;
    catalogFingerprintRef.current = `${catalog.version}\u0000${catalog.updated_at ?? ""}`;
  }, [catalog?.version, catalog?.updated_at]);

  useEffect(() => {
    if (!token) {
      setError("Нет токена — выполните вход.");
      return;
    }
    void (async () => {
      try {
        const me = await apiGet<Me>("/users/me", token);
        if (me.role !== "admin") {
          setError("Раздел «Правила» доступен только администратору.");
          return;
        }
        setAdminOk(true);
        try {
          await Promise.all([loadCatalog(token), refreshCoverageMeta(token).catch(() => null)]);
        } catch {
          setError("Не удалось загрузить активный каталог правил.");
        }
      } catch {
        setError("Не удалось проверить права пользователя.");
      }
    })();
  }, [token, loadCatalog, refreshCoverageMeta]);

  useEffect(() => {
    if (!token || !adminOk) return;
    const activeToken = token;
    let cancelled = false;
    let noteClearId: number | null = null;

    async function poll() {
      try {
        const cov = await refreshCoverageMeta(activeToken);
        if (cancelled || !cov) return;
        const nextFp = `${cov.catalog_version}\u0000${cov.catalog_updated_at ?? ""}`;
        const prevFp = catalogFingerprintRef.current;
        if (prevFp !== null && nextFp !== prevFp) {
          setAutoRefreshNote("Обнаружено обновление каталога, загружаем…");
          try {
            await loadCatalog(activeToken);
            setAutoRefreshNote("Каталог обновлён автоматически.");
            if (noteClearId !== null) window.clearTimeout(noteClearId);
            noteClearId = window.setTimeout(() => {
              if (!cancelled) setAutoRefreshNote(null);
            }, 4000);
          } catch {
            setAutoRefreshNote("Не удалось подтянуть новый каталог. Обновите страницу.");
          }
        }
      } catch {
        /* сеть / 401 — не спамим */
      }
    }

    void poll();
    const id = window.setInterval(() => void poll(), POLL_MS);
    const onVis = () => {
      if (document.visibilityState === "visible") void poll();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      cancelled = true;
      if (noteClearId !== null) window.clearTimeout(noteClearId);
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [token, adminOk, loadCatalog, refreshCoverageMeta]);

  const aiCodes = useMemo(() => {
    const set = new Set<string>();
    for (const rule of catalog?.rules ?? []) {
      if (rule.check_type === "ai_assisted") {
        set.add(rule.rule_code);
      }
    }
    return set;
  }, [catalog]);

  const appendixCodes = useMemo(() => new Set(coverageMeta?.ai_appendix_rule_codes ?? []), [coverageMeta]);

  const rows = useMemo(() => {
    const list = [...(catalog?.rules ?? [])];
    list.sort((a, b) => {
      if (a.level !== b.level) return a.level.localeCompare(b.level);
      return a.rule_name.localeCompare(b.rule_name, "ru");
    });
    return list;
  }, [catalog]);

  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Каталог правил аудита</h1>
          <p className="text-sm text-muted-foreground">
            Активная версия: <span className="font-medium">{catalog?.version ?? "-"}</span>
            {catalog?.updated_at ? (
              <>
                {" "}
                · обновлён в БД:{" "}
                <span className="font-medium">
                  {new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(
                    new Date(catalog.updated_at),
                  )}
                </span>
              </>
            ) : null}
          </p>
          <p className="text-xs text-muted-foreground">
            Страница сама подтягивает каталог при смене версии или даты обновления в БД (около раз в {POLL_MS / 1000}{" "}
            с и при возврате на вкладку).
          </p>
        </div>
        <AppSectionNav current="rules" />
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {autoRefreshNote ? <p className="text-sm text-blue-700">{autoRefreshNote}</p> : null}

      {adminOk && !error ? (
        <section className="rounded border p-4">
          <h2 className="mb-2 text-lg font-medium">Публикация каталога</h2>
          <p className="mb-3 text-sm text-muted-foreground">
            Загрузить в образе бэкенда <code className="rounded bg-muted px-1">rule-catalog.json</code> в базу и активировать
            (как в разделе «Настройки»).
          </p>
          <PublishBundledCatalogBlock
            token={token}
            onPublished={async () => {
              setError(null);
              const t = getAccessToken();
              if (!t) return;
              try {
                await Promise.all([loadCatalog(t), refreshCoverageMeta(t)]);
              } catch {
                setError("Не удалось обновить список правил после публикации.");
              }
            }}
          />
        </section>
      ) : null}

      {catalog ? (
        <section className="overflow-x-auto rounded border">
          <table className="min-w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-3 py-2 text-left">Название проверки</th>
                <th className="px-3 py-2 text-left">Описание</th>
                <th className="px-3 py-2 text-left">Рекомендации по исправлению</th>
                <th className="px-3 py-2 text-left" title="Да — в каталоге есть ai_assisted с тем же rule_code, или для кода задан шаблон AI-промпта на сервере (см. ai_appendix_rule_codes в API coverage). Реальный вызов Polza только при наличии ai_assisted в активном каталоге.">
                  AI после deterministic
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((rule) => {
                const hasAiRow = rule.check_type === "deterministic" && aiCodes.has(rule.rule_code);
                const hasAppendix = rule.check_type === "deterministic" && appendixCodes.has(rule.rule_code);
                const aiCell =
                  rule.check_type !== "deterministic"
                    ? "—"
                    : hasAiRow
                      ? "Да (ai_assisted в каталоге)"
                      : hasAppendix
                        ? "Да (шаблон промпта)"
                        : "Нет";
                return (
                  <tr key={`${rule.check_type}:${rule.rule_code}:${rule.level}`} className="border-t align-top">
                    <td className="px-3 py-2">
                      <div className="font-medium">{rule.rule_name}</div>
                      <div className="text-xs text-muted-foreground">
                        {rule.level} · {rule.rule_code} · {rule.check_type}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{ruleDescription(rule)}</td>
                    <td className="px-3 py-2 text-muted-foreground">{ruleRecommendation(rule)}</td>
                    <td className="px-3 py-2">{aiCell}</td>
                  </tr>
                );
              })}
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-3 py-6 text-muted-foreground">
                    Нет правил в активном каталоге.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </section>
      ) : null}
    </main>
  );
}
