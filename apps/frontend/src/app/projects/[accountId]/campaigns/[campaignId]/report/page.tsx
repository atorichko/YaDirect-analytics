"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { SiteHelpLink } from "@/components/site-help-link";
import { Button } from "@/components/ui/button";
import { apiGet, apiPost } from "@/lib/api-client";
import { getAccessToken } from "@/lib/auth";
import { ruleTitleRu } from "@/lib/rule-titles-ru";

type Campaign = { id: string; name: string | null };
type JobResponse = { task_id: string; task_name: string; status: string };
type JobStatus = {
  task_id: string;
  state: string;
  ready: boolean;
  successful: boolean | null;
  progress_percent: number | null;
  current_step: string | null;
};

type Finding = {
  id: string;
  rule_code: string;
  rule_name: string;
  severity: string;
  level: string;
  group_external_id?: string | null;
  ad_external_id?: string | null;
  campaign_external_id?: string | null;
  issue_location: string;
  evidence?: Record<string, unknown> | null;
  impact_ru: string;
  recommendation_ru: string;
  status: string;
  ai_verdict?: Record<string, unknown> | null;
  created_at: string;
};

type GroupedModerationAd = {
  adId: string;
  adTitle: string;
};

type DisplayRow = Finding & {
  groupedModerationAds?: GroupedModerationAd[];
};

type ActiveCatalogRule = {
  rule_code: string;
  fix_recommendation?: string | null;
};

type ActiveCatalogResponse = {
  rules: ActiveCatalogRule[];
};

const RULE_ACTIVE_AD_REJECTED_OR_RESTRICTED = "ACTIVE_AD_REJECTED_OR_RESTRICTED";
const RULE_ACTIVE_CAMPAIGN_WITHOUT_ACTIVE_GROUPS = "ACTIVE_CAMPAIGN_WITHOUT_ACTIVE_GROUPS";

const EVIDENCE_LABEL_RU: Record<string, string> = {
  campaign_id: "Кампания",
  campaign_name: "Название кампании",
  group_id: "Группа",
  group_name: "Название группы",
  ad_id: "Объявление",
  keyword_id: "Ключ",
  keyword_text: "Фраза",
  keywords: "Фразы",
  keyword_ids: "ID фраз",
  normalized_keyword: "Нормализованная фраза",
  active_group_count: "Активных групп",
  groups_in_snapshot: "Группы в снимке",
  url_field: "Поле URL",
  url_value: "URL",
  checked_url: "Проверенный URL",
  final_url: "Итоговый URL",
  status_code: "HTTP-код",
  network_error: "Сеть",
  missing_utm_params: "Нет UTM",
  utm_validation_errors: "Ошибки UTM",
  redirect_chain: "Цепочка редиректов",
  broken_sitelinks: "Битые быстрые ссылки",
  conflicting_negative: "Конфликт минус-слова",
  conflict_tokens: "Конфликтующие токены",
  missing_negative_tokens: "Нужны минус-слова",
  overlap_keywords: "Пересечения",
  ad_ids: "Объявления",
  left_group_id: "Группа А",
  right_group_id: "Группа Б",
  semantic_overlap_examples: "Примеры пересечений",
};

function evidenceLabel(key: string): string {
  return EVIDENCE_LABEL_RU[key] ?? key;
}

function statusWordRu(value: unknown): string {
  const raw = String(value ?? "").toLowerCase();
  if (raw === "paused") return "Пауза";
  if (raw === "active") return "Активна";
  if (raw === "archived") return "Архив";
  if (raw === "stopped") return "Остановлена";
  return String(value ?? "—");
}

function formatEvidenceValue(key: string, v: unknown): React.ReactNode {
  if (v === null || v === undefined) return "—";
  if (key === "groups_in_snapshot" && Array.isArray(v)) {
    return (
      <ul className="mt-1 list-inside list-disc space-y-0.5">
        {(v as Record<string, unknown>[]).map((g, i) => (
          <li key={i}>
            ID {(g.group_id ?? g.id) as string}
            {g.group_name ? ` — ${String(g.group_name)}` : ""}
            {g.status != null ? ` — статус: ${String(g.status)}` : ""}
          </li>
        ))}
      </ul>
    );
  }
  if (Array.isArray(v)) {
    if (v.length > 0 && typeof v[0] === "object") {
      return (
        <ul className="mt-1 list-inside list-disc space-y-0.5 font-mono text-[11px]">
          {v.map((item, i) => (
            <li key={i}>{JSON.stringify(item)}</li>
          ))}
        </ul>
      );
    }
    return (v as unknown[]).map((x) => String(x)).join(", ");
  }
  if (typeof v === "object") {
    return <pre className="mt-1 max-h-40 overflow-auto rounded bg-muted/50 p-2 text-[11px]">{JSON.stringify(v, null, 2)}</pre>;
  }
  return String(v);
}

function EvidenceBlock({ row }: { row: Finding }) {
  const ev = row.evidence ?? undefined;
  if (!ev || Object.keys(ev).length === 0) {
    return <p className="text-xs text-muted-foreground">Нет структурированных подсказок по объектам.</p>;
  }
  if (row.rule_code === RULE_ACTIVE_CAMPAIGN_WITHOUT_ACTIVE_GROUPS) {
    const campaignId = String(ev.campaign_id ?? "—");
    const campaignName = String(ev.campaign_name ?? "—");
    const groups = Array.isArray(ev.groups_in_snapshot) ? (ev.groups_in_snapshot as Record<string, unknown>[]) : [];
    const stoppedGroups = groups
      .filter((item) => String(item.status ?? "").toLowerCase() === "paused")
      .map((item) => `ID ${String(item.group_id ?? item.id ?? "—")} — Статус: ${statusWordRu(item.status)}`);
    return (
      <dl className="space-y-2 text-xs">
        <div>
          <dt className="font-medium text-foreground">Кампания</dt>
          <dd className="text-muted-foreground">
            {campaignId} / {campaignName}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-foreground">Остановленные группы</dt>
          <dd className="text-muted-foreground">
            {stoppedGroups.length > 0 ? stoppedGroups.join("; ") : "Нет"}
          </dd>
        </div>
      </dl>
    );
  }
  return (
    <dl className="space-y-2 text-xs">
      {Object.entries(ev).map(([k, v]) => {
        if (v === null || v === undefined || v === "") return null;
        return (
          <div key={k}>
            <dt className="font-medium text-foreground">{evidenceLabel(k)}</dt>
            <dd className="text-muted-foreground">{formatEvidenceValue(k, v)}</dd>
          </div>
        );
      })}
    </dl>
  );
}

export default function CampaignReportPage() {
  const params = useParams<{ accountId: string; campaignId: string }>();
  const accountId = params.accountId;
  const campaignId = decodeURIComponent(params.campaignId);
  const token = useMemo(() => getAccessToken(), []);
  const [rows, setRows] = useState<Finding[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [campaignName, setCampaignName] = useState<string | null>(null);
  const [showFixed, setShowFixed] = useState(false);
  const [auditTaskId, setAuditTaskId] = useState<string | null>(null);
  const [auditStatus, setAuditStatus] = useState<string | null>(null);
  const [auditRunning, setAuditRunning] = useState(false);
  const [catalogRecommendations, setCatalogRecommendations] = useState<Record<string, string>>({});
  const levels = ["L1", "L2", "L3", "AI"] as const;

  useEffect(() => {
    if (typeof document !== "undefined") {
      const campaignTitle = campaignName ?? campaignId;
      document.title = `Отчет кампании ${campaignTitle} | YaDirect Analytics`;
    }
  }, [campaignId, campaignName]);

  async function loadReport(activeToken: string) {
    const [findings, campaigns, activeCatalog] = await Promise.all([
      apiGet<Finding[]>(`/findings?account_id=${accountId}&campaign_id=${encodeURIComponent(campaignId)}&limit=500`, activeToken),
      apiGet<Campaign[]>(`/ad-accounts/${accountId}/campaigns`, activeToken),
      apiGet<ActiveCatalogResponse>("/rule-catalogs/active", activeToken),
    ]);
    setRows(findings);
    setCampaignName(campaigns.find((x) => x.id === campaignId)?.name ?? null);
    const recMap: Record<string, string> = {};
    for (const rule of activeCatalog.rules ?? []) {
      const text = String(rule.fix_recommendation ?? "").trim();
      if (text) recMap[rule.rule_code] = text;
    }
    setCatalogRecommendations(recMap);
  }

  useEffect(() => {
    if (!token) return;
    void (async () => {
      try {
        await loadReport(token);
      } catch (e) {
        if (e instanceof Error && e.message === "UNAUTHORIZED") return;
        setError("Не удалось загрузить отчет кампании.");
      }
    })();
  }, [accountId, campaignId, token]);

  const latestRows = useMemo(() => {
    const byKey = new Map<string, Finding>();
    const sorted = [...rows].sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at));
    for (const row of sorted) {
      const key = [
        row.rule_code,
        row.issue_location,
        String(row.evidence?.group_id ?? ""),
        String(row.evidence?.normalized_keyword ?? ""),
        row.group_external_id ?? "",
      ].join("|");
      if (!byKey.has(key)) {
        byKey.set(key, row);
      }
    }
    return Array.from(byKey.values());
  }, [rows]);

  const visibleRows = useMemo(
    () => latestRows.filter((row) => (showFixed ? true : row.status !== "fixed")),
    [latestRows, showFixed],
  );
  const displayRows = useMemo<DisplayRow[]>(() => {
    const moderationRows = visibleRows.filter((row) => row.rule_code === RULE_ACTIVE_AD_REJECTED_OR_RESTRICTED);
    const restRows = visibleRows.filter((row) => row.rule_code !== RULE_ACTIVE_AD_REJECTED_OR_RESTRICTED);
    if (moderationRows.length === 0) return restRows;

    const [leader, ...others] = moderationRows;
    const groupedByAd = new Map<string, GroupedModerationAd>();
    for (const item of [leader, ...others]) {
      const adIdRaw = item.ad_external_id ?? item.evidence?.ad_id;
      if (!adIdRaw) continue;
      const adId = String(adIdRaw);
      const adTitleRaw = item.evidence?.ad_title;
      const adTitle = String(adTitleRaw ?? "").trim() || "Название объявления недоступно";
      if (!groupedByAd.has(adId)) {
        groupedByAd.set(adId, { adId, adTitle });
      }
    }

    const groupedModeration: DisplayRow = {
      ...leader,
      groupedModerationAds: Array.from(groupedByAd.values()).sort((a, b) => a.adId.localeCompare(b.adId)),
    };
    return [groupedModeration, ...restRows];
  }, [visibleRows]);
  const fixedHiddenCount = useMemo(() => {
    if (showFixed) return 0;
    return latestRows.filter((row) => row.status === "fixed" && !row.ai_verdict).length;
  }, [latestRows, showFixed]);

  const countByLevel = useMemo(() => {
    const m: Record<string, number> = { L1: 0, L2: 0, L3: 0, AI: 0 };
    for (const row of displayRows) {
      m[row.level] = (m[row.level] ?? 0) + 1;
    }
    return m;
  }, [displayRows]);

  function severityRu(v: string) {
    if (v === "critical") return "Критично";
    if (v === "high") return "Высокая";
    return "Предупреждение";
  }

  function statusRu(v: string) {
    if (v === "new") return "Новая";
    if (v === "fixed") return "Исправлено";
    if (v === "existing") return "Ранее найдено";
    if (v === "reopened") return "Повторно открыто";
    if (v === "ignored") return "Игнор";
    if (v === "false_positive") return "Ложное срабатывание";
    return v;
  }

  function levelDescription(lvl: string): string {
    if (lvl === "L1") return "Структура, семантика, модерация, расширения (без внешних HTTP-проверок).";
    if (lvl === "L2") return "Стратегии, Метрика, цели, обучение, бюджетные ограничения.";
    if (lvl === "L3") return "Технические проверки URL, редиректов, SSL и UTM.";
    if (lvl === "AI") return "Дополнительный разбор с помощью модели (эвристики и формулировки).";
    return "";
  }

  async function runCampaignAudit() {
    if (!token) return;
    try {
      setError(null);
      setAuditRunning(true);
      const result = await apiPost<JobResponse>("/audits/campaign/run-job", token, {
        account_id: accountId,
        campaign_id: campaignId,
      });
      setInfo(`Аудит кампании запущен (${result.task_id}).`);
      setAuditTaskId(result.task_id);
      setAuditStatus("Аудит запущен...");
    } catch (err) {
      if (err instanceof Error && err.message === "UNAUTHORIZED") return;
      const text = err instanceof Error ? err.message : String(err);
      setError(`Не удалось запустить аудит: ${text}`);
      setAuditRunning(false);
    }
  }

  useEffect(() => {
    if (!token || !auditTaskId) return;
    const timer = window.setInterval(() => {
      void (async () => {
        try {
          const status = await apiGet<JobStatus>(`/audits/jobs/${auditTaskId}`, token);
          if (!status.ready) {
            const step = status.current_step ?? "Выполняется аудит...";
            const pct = typeof status.progress_percent === "number" ? status.progress_percent : 0;
            setAuditStatus(`${step} · ${pct}%`);
            return;
          }
          if (status.successful) {
            setAuditStatus("Аудит завершен.");
            await loadReport(token);
          } else {
            setAuditStatus("Аудит завершился с ошибкой.");
          }
          setAuditTaskId(null);
          setAuditRunning(false);
        } catch {
          // ignore transient poll errors
        }
      })();
    }, 2500);
    return () => window.clearInterval(timer);
  }, [auditTaskId, token]);

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 px-6 py-10">
      <div className="flex items-center justify-between">
        <div>
          <p className="mb-1 text-xs text-muted-foreground">
            <Link href="/dashboard" className="hover:underline">
              Аккаунты
            </Link>{" "}
            /{" "}
            <Link href={`/projects/${accountId}`} className="hover:underline">
              Проект
            </Link>{" "}
            / <span>Отчет кампании</span>
          </p>
          <h1 className="text-2xl font-semibold tracking-tight">Отчет кампании: {campaignName ?? campaignId}</h1>
          <p className="text-sm text-muted-foreground">ID кампании: {campaignId}</p>
        </div>
        <div className="flex items-center gap-2">
          <SiteHelpLink />
          <span className={auditRunning || auditTaskId ? "audit-play-running inline-flex rounded-md" : "inline-flex"}>
            <Button onClick={() => void runCampaignAudit()} disabled={auditRunning || !!auditTaskId}>
              ▶ Запустить аудит
            </Button>
          </span>
        </div>
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {info ? <p className="text-sm text-emerald-600">{info}</p> : null}
      {auditStatus ? <p className="text-sm text-blue-700">{auditStatus}</p> : null}
      {fixedHiddenCount > 0 ? (
        <p className="text-sm text-muted-foreground">
          Скрыто исправленных записей: {fixedHiddenCount}. Показываем только актуальные проблемы.
        </p>
      ) : null}
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={showFixed} onChange={(e) => setShowFixed(e.target.checked)} />
        Показывать исправленные
      </label>
      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {levels.map((lvl) => (
          <div key={lvl} className="rounded border p-3">
            <p className="text-xs text-muted-foreground">Уровень</p>
            <p className="text-lg font-semibold">{lvl}</p>
            <p className="text-sm text-muted-foreground">Найдено: {countByLevel[lvl] ?? 0}</p>
            <p className="mt-1 text-[11px] leading-snug text-muted-foreground">{levelDescription(lvl)}</p>
          </div>
        ))}
      </section>

      <div className="overflow-x-auto rounded border">
        <table className="min-w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-3 py-2 text-left">Замечание (нажмите для подробностей)</th>
            </tr>
          </thead>
          <tbody>
            {displayRows.map((row) => {
              const title = ruleTitleRu(row.rule_code, row.rule_name);
              const isModerationRule = row.rule_code === RULE_ACTIVE_AD_REJECTED_OR_RESTRICTED;
              const loc = [
                row.campaign_external_id ? `камп. ${row.campaign_external_id}` : null,
                row.group_external_id ? `гр. ${row.group_external_id}` : null,
                row.ad_external_id ? `объявл. ${row.ad_external_id}` : null,
              ]
                .filter(Boolean)
                .join(", ");
              return (
                <tr key={row.id} className="border-t">
                  <td className="px-3 py-2 align-top">
                    <details className="group rounded-md border border-transparent open:border-border open:bg-muted/30">
                      <summary className="cursor-pointer list-none px-1 py-2 [&::-webkit-details-marker]:hidden">
                        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                          <span className="text-sm font-semibold">{title}</span>
                          <span className="text-xs text-muted-foreground">{severityRu(row.severity)}</span>
                          <span className="text-xs text-muted-foreground">{row.level}</span>
                          <span className={row.status === "existing" ? "text-xs font-semibold text-red-600" : "text-xs text-muted-foreground"}>
                            {statusRu(row.status)}
                          </span>
                          {loc && !isModerationRule ? <span className="text-xs text-blue-800">Объекты: {loc}</span> : null}
                          <span className="ml-auto text-xs text-muted-foreground">
                            {new Date(row.created_at).toLocaleString("ru-RU")}
                          </span>
                        </div>
                        <p className="mt-1 text-sm text-foreground">{row.impact_ru}</p>
                      </summary>
                      <div className="border-t px-3 py-2">
                        <p className="text-xs font-medium text-muted-foreground">Рекомендация</p>
                        {isModerationRule ? (
                          <>
                            <p className="text-sm">Исправить объявление по замечаниям модерации.</p>
                            <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
                            <div className="text-sm text-foreground">
                              <p>Объявления, не прошедшие модерацию:</p>
                              <ul className="mt-1 list-inside list-disc">
                                {(row.groupedModerationAds ?? []).map((item) => (
                                  <li key={item.adId}>
                                    {item.adId} - {item.adTitle}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </>
                        ) : (
                          <>
                            <p className="text-sm">{catalogRecommendations[row.rule_code] ?? row.recommendation_ru}</p>
                            <p className="mt-2 text-xs font-medium text-muted-foreground">Детали (снимок аудита)</p>
                            <EvidenceBlock row={row} />
                          </>
                        )}
                      </div>
                    </details>
                  </td>
                </tr>
              );
            })}
            {displayRows.length === 0 ? (
              <tr>
                <td className="px-3 py-6 text-muted-foreground">По кампании пока нет находок.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <section className="rounded border bg-muted/20 p-4 text-sm">
        <h2 className="mb-2 font-medium">Легенда уровней проверки</h2>
        <ul className="list-inside list-disc space-y-1 text-muted-foreground">
          <li>
            <strong className="text-foreground">L1</strong> — {levelDescription("L1")}
          </li>
          <li>
            <strong className="text-foreground">L2</strong> — {levelDescription("L2")}
          </li>
          <li>
            <strong className="text-foreground">L3</strong> — {levelDescription("L3")}
          </li>
          <li>
            <strong className="text-foreground">AI</strong> — {levelDescription("AI")}
          </li>
        </ul>
      </section>
    </main>
  );
}
