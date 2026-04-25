"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { AppSectionNav } from "@/components/app-section-nav";
import { Button } from "@/components/ui/button";
import { apiGet, apiPost } from "@/lib/api-client";
import { getAccessToken } from "@/lib/auth";
import { ruleTitleRu } from "@/lib/rule-titles-ru";
import { dnaAccountHref, dnaBannerHref, dnaCampaignHref, dnaGroupHref } from "@/lib/yandex-dna-links";

import {
  AiVerdictPanel,
  buildGroupedCampaignRows,
  GroupedDetailsSection,
  recommendationText,
  rowUsesGroupedLayout,
  type CampaignFinding,
  type DisplayRow,
} from "./report-grouping";

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

type Finding = CampaignFinding;

type AdAccountRow = { id: string; login: string };

type EvidenceLinkCtx = {
  yandexLogin: string | null;
  pageCampaignId: string;
  row: Finding;
  ev: Record<string, unknown>;
};

type ActiveCatalogRule = {
  rule_code: string;
  fix_recommendation?: string | null;
};

type ActiveCatalogResponse = {
  rules: ActiveCatalogRule[];
};

const RULE_ACTIVE_CAMPAIGN_WITHOUT_ACTIVE_GROUPS = "ACTIVE_CAMPAIGN_WITHOUT_ACTIVE_GROUPS";

const EVIDENCE_LABEL_RU: Record<string, string> = {
  campaign_id: "Кампания",
  campaign_name: "Название кампании",
  group_id: "Группа",
  group_name: "Название группы",
  ad_id: "Объявление",
  sample_ad_id: "Пример объявления",
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
  redirect_chain_flow_ru: "Переходы (кто куда ведёт)",
  broken_sitelinks: "Битые быстрые ссылки",
  broken_sitelink_urls: "Битые быстрые ссылки (URL)",
  main_url: "Основной URL",
  main_domain: "Домен объявления",
  sitelink_urls: "Быстрые ссылки",
  sitelink_domains: "Домены быстрых ссылок (несовпадение)",
  utm_param_status: "Статус UTM-параметров",
  utm_issue_details: "Детали ошибок UTM",
  url_syntax_issues: "Проблемы синтаксиса URL",
  url_value_segments: "URL (фрагменты)",
  query_highlight_segments: "Query-строка (ошибки)",
  empty_or_technical_values: "Пустые/технические значения",
  https_available: "HTTPS доступен",
  ssl_error: "Ошибка SSL",
  redirect_hops: "Количество редиректов",
  matched_date_text: "Найденный фрагмент даты",
  parsed_date: "Распознанная дата",
  matched_placeholders: "Все плейсхолдеры",
  conflicting_negative: "Конфликт минус-слова",
  conflict_tokens: "Конфликтующие токены",
  missing_negative_tokens: "Нужны минус-слова",
  overlap_keywords: "Пересечения",
  ad_ids: "Объявления",
  left_group_id: "Группа А",
  right_group_id: "Группа Б",
  semantic_overlap_examples: "Примеры пересечений",
  display_url_full: "Полный URL",
  url_query_highlight_segments: "Query-строка (проблема)",
  url_highlight_segments: "URL (плейсхолдер)",
  full_url_highlight_segments: "URL (синтаксис)",
  text_highlight_segments: "Текст (ошибка)",
  ad_text_for_audit: "Текст объявления",
  issue_explanation_ru: "Пояснение",
  audit_reference_today: "Дата проверки (ISO)",
  audit_reference_today_ru: "Сегодня по аудиту",
  text_geo_surfaces: "Город в тексте (как написано)",
  cross_minus_phrase_examples: "Примеры пересечений (кросс-минус)",
  pattern_sample_urls: "Примеры URL по шаблонам UTM",
  campaigns_with_mixed_patterns: "Кампании с разной UTM",
  conflict_detail_ru: "В чём конфликт гео",
  campaign_targeting_summary_ru: "Геотаргетинг кампании (сводка)",
  mentioned_city_label_ru: "Город в тексте (нормализовано)",
  campaign_geo_labels: "Метки гео кампании",
  scope: "Область",
  main_url_display: "Основная ссылка (отображение)",
  sitelink_urls_mismatched: "Быстрые ссылки (другой домен)",
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

function SegmentList({ segments }: { segments: Array<{ text?: string; ok?: boolean }> }) {
  return (
    <p className="mt-1 break-all font-mono text-[11px] leading-relaxed">
      {segments.map((seg, i) => (
        <span key={i} className={seg.ok === false ? "text-destructive font-medium" : "text-muted-foreground"}>
          {seg.text ?? ""}
        </span>
      ))}
    </p>
  );
}

const EVIDENCE_SEGMENT_KEYS = new Set([
  "url_value_segments",
  "query_highlight_segments",
  "url_query_highlight_segments",
  "url_highlight_segments",
  "full_url_highlight_segments",
  "text_highlight_segments",
]);

function tryScalarDnaLink(key: string, v: unknown, ctx: EvidenceLinkCtx): ReactNode | null {
  const login = ctx.yandexLogin;
  if (!login || typeof v !== "string") return null;
  const id = v.trim();
  if (!/^\d+$/.test(id)) return null;
  const ev = ctx.ev;
  const row = ctx.row;

  const aCls = "text-blue-700 underline underline-offset-2";
  if (key === "campaign_id" || key === "left_campaign_id" || key === "right_campaign_id") {
    return (
      <a className={aCls} href={dnaCampaignHref(login, id)} target="_blank" rel="noreferrer">
        {id}
      </a>
    );
  }
  if (key === "group_id" || key === "left_group_id" || key === "right_group_id") {
    let cid = "";
    if (key === "left_group_id") {
      cid = String(
        ev.left_campaign_id ?? ev.campaign_id ?? row.campaign_external_id ?? ctx.pageCampaignId ?? "",
      ).trim();
    } else if (key === "right_group_id") {
      cid = String(
        ev.right_campaign_id ?? ev.campaign_id ?? row.campaign_external_id ?? ctx.pageCampaignId ?? "",
      ).trim();
    } else {
      cid = String(ev.campaign_id ?? row.campaign_external_id ?? ctx.pageCampaignId ?? "").trim();
    }
    if (!cid || !/^\d+$/.test(cid)) return null;
    return (
      <a className={aCls} href={dnaGroupHref(login, cid, id)} target="_blank" rel="noreferrer">
        {id}
      </a>
    );
  }
  if (key === "ad_id") {
    const cid = String(row.campaign_external_id ?? ev.campaign_id ?? ctx.pageCampaignId ?? "").trim();
    const gid = String(row.group_external_id ?? ev.group_id ?? "").trim();
    if (!cid || !gid || !/^\d+$/.test(cid) || !/^\d+$/.test(gid)) return null;
    return (
      <a className={aCls} href={dnaBannerHref(login, cid, gid, id)} target="_blank" rel="noreferrer">
        {id}
      </a>
    );
  }
  if (key === "sample_ad_id") {
    const cid = String(row.campaign_external_id ?? ev.campaign_id ?? ctx.pageCampaignId ?? "").trim();
    const gid = String(row.group_external_id ?? ev.group_id ?? "").trim();
    if (!cid || !gid || !/^\d+$/.test(cid) || !/^\d+$/.test(gid)) return null;
    return (
      <a className={aCls} href={dnaBannerHref(login, cid, gid, id)} target="_blank" rel="noreferrer">
        {id}
      </a>
    );
  }
  return null;
}

function formatEvidenceValue(key: string, v: unknown, linkCtx?: EvidenceLinkCtx): ReactNode {
  if (v === null || v === undefined) return "—";
  if (
    key === "ad_ids" &&
    Array.isArray(v) &&
    v.length > 0 &&
    typeof v[0] !== "object" &&
    linkCtx?.yandexLogin
  ) {
    const login = linkCtx.yandexLogin;
    const ev = linkCtx.ev;
    const row = linkCtx.row;
    const cid = String(row.campaign_external_id ?? ev.campaign_id ?? linkCtx.pageCampaignId ?? "").trim();
    const gid = String(row.group_external_id ?? ev.group_id ?? "").trim();
    const aCls = "text-blue-700 underline underline-offset-2";
    if (/^\d+$/.test(cid) && /^\d+$/.test(gid)) {
      return (
        <ul className="mt-1 list-inside list-disc space-y-0.5 font-mono text-[11px]">
          {(v as unknown[]).map((x, i) => {
            const aid = String(x ?? "").trim();
            if (!/^\d+$/.test(aid)) {
              return (
                <li key={i}>
                  <span className="text-muted-foreground">{aid}</span>
                </li>
              );
            }
            return (
              <li key={i}>
                <a className={aCls} href={dnaBannerHref(login, cid, gid, aid)} target="_blank" rel="noreferrer">
                  {aid}
                </a>
              </li>
            );
          })}
        </ul>
      );
    }
  }
  if (linkCtx?.yandexLogin && typeof v === "string") {
    const linked = tryScalarDnaLink(key, v, linkCtx);
    if (linked) return linked;
  }
  if (
    EVIDENCE_SEGMENT_KEYS.has(key) &&
    Array.isArray(v) &&
    v.length > 0 &&
    typeof v[0] === "object"
  ) {
    return <SegmentList segments={v as Array<{ text?: string; ok?: boolean }>} />;
  }
  if (
    (key === "issue_explanation_ru" ||
      key === "conflict_detail_ru" ||
      key === "redirect_chain_flow_ru") &&
    typeof v === "string"
  ) {
    return (
      <p className="mt-1 break-all text-sm text-foreground/95 sm:break-words">{v}</p>
    );
  }
  if (key === "cross_minus_phrase_examples" && Array.isArray(v)) {
    return (
      <ul className="mt-1 list-inside list-disc space-y-1 text-[11px]">
        {(v as Record<string, unknown>[]).map((row, i) => (
          <li key={i}>
            <span className="text-muted-foreground">{String(row.label ?? "пример")}: </span>
            «{String(row.phrase ?? "")}» — токен <span className="text-destructive">{String(row.shared_token ?? "")}</span>
          </li>
        ))}
      </ul>
    );
  }
  if (key === "sitelink_urls" && Array.isArray(v)) {
    return (
      <ul className="mt-1 list-inside list-disc space-y-1 font-mono text-[11px]">
        {(v as Record<string, unknown>[]).map((row, i) => (
          <li key={i} className={row.matches_main_domain === false ? "text-destructive" : ""}>
            {String(row.url ?? "")}
            {row.domain != null ? ` — домен: ${String(row.domain)}` : ""}
            {row.matches_main_domain === false ? " (не совпадает с основным)" : ""}
          </li>
        ))}
      </ul>
    );
  }
  if (key === "utm_issue_details" && Array.isArray(v)) {
    return (
      <ul className="mt-1 list-inside list-disc space-y-0.5 text-[11px]">
        {(v as Record<string, unknown>[]).map((row, i) => (
          <li key={i}>
            <span className="text-destructive">{String(row.code ?? "")}</span>
            {row.param ? ` — ${String(row.param)}` : ""}: {String(row.issue ?? "")}
          </li>
        ))}
      </ul>
    );
  }
  if (key === "utm_param_status" && Array.isArray(v)) {
    return (
      <ul className="mt-1 list-inside list-disc space-y-0.5 font-mono text-[11px]">
        {(v as Record<string, unknown>[]).map((row, i) => (
          <li key={i} className={row.present === false ? "text-destructive" : ""}>
            {String(row.param ?? "")}: {row.present === false ? "отсутствует" : String(row.value ?? "—")}
          </li>
        ))}
      </ul>
    );
  }
  if (key === "broken_sitelink_urls" && Array.isArray(v)) {
    return (
      <ul className="mt-1 list-inside list-disc space-y-1 break-all font-mono text-[11px]">
        {(v as Record<string, unknown>[]).map((row, i) => (
          <li key={i}>
            {row.sitelink_id != null ? <span className="text-muted-foreground">ID {String(row.sitelink_id)} — </span> : null}
            <span className="text-destructive">{String(row.url ?? "")}</span>
          </li>
        ))}
      </ul>
    );
  }
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

function reportRowLocLinks(row: DisplayRow, pageCampaignId: string, login: string | null): ReactNode {
  const aCls = "text-blue-700 underline underline-offset-2";
  const parts: ReactNode[] = [];
  if (row.campaign_external_id) {
    const cid = String(row.campaign_external_id);
    parts.push(
      login && /^\d+$/.test(cid) ? (
        <a key="c" className={aCls} href={dnaCampaignHref(login, cid)} target="_blank" rel="noreferrer">
          камп. {cid}
        </a>
      ) : (
        <span key="c">камп. {cid}</span>
      ),
    );
  } else if (row.issue_location?.startsWith("account:")) {
    parts.push(<span key="a">{row.issue_location}</span>);
  }
  if (row.group_external_id) {
    const gid = String(row.group_external_id);
    const cid = String(row.campaign_external_id ?? pageCampaignId);
    parts.push(
      login && /^\d+$/.test(cid) && /^\d+$/.test(gid) ? (
        <a key="g" className={aCls} href={dnaGroupHref(login, cid, gid)} target="_blank" rel="noreferrer">
          гр. {gid}
        </a>
      ) : (
        <span key="g">гр. {gid}</span>
      ),
    );
  }
  if (row.ad_external_id) {
    const aid = String(row.ad_external_id);
    const cid = String(row.campaign_external_id ?? pageCampaignId);
    const gid = String(row.group_external_id ?? "");
    parts.push(
      login && /^\d+$/.test(cid) && /^\d+$/.test(gid) && /^\d+$/.test(aid) ? (
        <a key="b" className={aCls} href={dnaBannerHref(login, cid, gid, aid)} target="_blank" rel="noreferrer">
          объявл. {aid}
        </a>
      ) : (
        <span key="b">объявл. {aid}</span>
      ),
    );
  }
  if (!parts.length) return null;
  return (
    <>
      {parts.map((p, i) => (
        <span key={i}>
          {i > 0 ? ", " : null}
          {p}
        </span>
      ))}
    </>
  );
}

function EvidenceBlock({
  row,
  yandexClientLogin,
  pageCampaignId,
}: {
  row: Finding;
  yandexClientLogin: string | null;
  pageCampaignId: string;
}) {
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
            {yandexClientLogin && /^\d+$/.test(campaignId) ? (
              <a
                className="text-blue-700 underline underline-offset-2"
                href={dnaCampaignHref(yandexClientLogin, campaignId)}
                target="_blank"
                rel="noreferrer"
              >
                {campaignId}
              </a>
            ) : (
              campaignId
            )}{" "}
            / {campaignName}
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
    <>
      <dl className="space-y-2 text-xs">
        {Object.entries(ev).map(([k, v]) => {
          if (v === null || v === undefined || v === "") return null;
          const linkCtx: EvidenceLinkCtx = {
            yandexLogin: yandexClientLogin,
            pageCampaignId,
            row,
            ev: ev as Record<string, unknown>,
          };
          return (
            <div key={k}>
              <dt className="font-medium text-foreground">{evidenceLabel(k)}</dt>
              <dd className="text-muted-foreground">{formatEvidenceValue(k, v, linkCtx)}</dd>
            </div>
          );
        })}
      </dl>
      <AiVerdictPanel rows={[row]} />
    </>
  );
}

export default function CampaignReportPage() {
  const params = useParams<{ accountId: string; campaignId: string }>();
  const accountKey = decodeURIComponent(params.accountId);
  const [resolvedAccountId, setResolvedAccountId] = useState<string | null>(null);
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
  const [yandexClientLogin, setYandexClientLogin] = useState<string | null>(null);
  /** Fallback если GET /ad-accounts не вернул login (один клиент на инсталляцию). Сборка: NEXT_PUBLIC_YANDEX_ULOGIN. */
  const defaultYandexUlogin = useMemo(
    () => (process.env.NEXT_PUBLIC_YANDEX_ULOGIN || "").trim() || null,
    [],
  );
  const effectiveYandexLogin = yandexClientLogin ?? defaultYandexUlogin;
  const levels = ["L1", "L2", "L3", "AI"] as const;

  useEffect(() => {
    if (typeof document !== "undefined") {
      const campaignTitle = campaignName ?? campaignId;
      document.title = `Отчет кампании ${campaignTitle} | YaDirect Analytics`;
    }
  }, [campaignId, campaignName]);

  async function loadReport(activeToken: string) {
    const accounts = await apiGet<AdAccountRow[]>("/ad-accounts", activeToken);
    const resolvedAccount =
      accounts.find((a) => a.id === accountKey) ??
      accounts.find((a) => String(a.login ?? "").trim().toLowerCase() === accountKey.toLowerCase());
    if (!resolvedAccount) {
      throw new Error("PROJECT_NOT_FOUND");
    }
    const accountId = resolvedAccount.id;
    setResolvedAccountId(accountId);
    const [findings, campaigns, activeCatalog] = await Promise.all([
      apiGet<Finding[]>(
        `/findings?account_id=${accountId}&campaign_id=${encodeURIComponent(campaignId)}&limit=500`,
        activeToken,
      ),
      apiGet<Campaign[]>(`/ad-accounts/${accountId}/campaigns`, activeToken),
      apiGet<ActiveCatalogResponse>("/rule-catalogs/active", activeToken),
    ]);
    setRows(findings);
    setCampaignName(campaigns.find((x) => x.id === campaignId)?.name ?? null);
    setYandexClientLogin(resolvedAccount.login?.trim() ? resolvedAccount.login.trim() : null);
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
  }, [accountKey, campaignId, token]);

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
  const displayRows = useMemo<DisplayRow[]>(
    () => buildGroupedCampaignRows(visibleRows, campaignId),
    [visibleRows, campaignId],
  );
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
    if (!resolvedAccountId) {
      setError("Не удалось определить аккаунт проекта. Обновите страницу.");
      return;
    }
    try {
      setError(null);
      setAuditRunning(true);
      const result = await apiPost<JobResponse>("/audits/campaign/run-job", token, {
        account_id: resolvedAccountId,
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
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="mb-1 text-xs text-muted-foreground">
            <Link href="/dashboard" className="hover:underline">
              Аккаунты
            </Link>{" "}
            /{" "}
            <Link href={`/projects/${encodeURIComponent(effectiveYandexLogin ?? accountKey)}`} className="hover:underline">
              Проект
            </Link>{" "}
            / <span>Отчет кампании</span>
          </p>
          <h1 className="text-2xl font-semibold tracking-tight">Отчет кампании: {campaignName ?? campaignId}</h1>
          <p className="text-sm text-muted-foreground">
            ID кампании:{" "}
            {effectiveYandexLogin && /^\d+$/.test(campaignId) ? (
              <a
                className="text-blue-700 underline underline-offset-2"
                href={dnaCampaignHref(effectiveYandexLogin, campaignId)}
                target="_blank"
                rel="noreferrer"
              >
                {campaignId}
              </a>
            ) : (
              campaignId
            )}
            {effectiveYandexLogin ? (
              <>
                {" "}
                ·{" "}
                <a
                  className="text-blue-700 underline underline-offset-2"
                  href={dnaAccountHref(effectiveYandexLogin)}
                  target="_blank"
                  rel="noreferrer"
                >
                  Аккаунт в Директе
                </a>
              </>
            ) : null}
          </p>
        </div>
        <AppSectionNav
          trailing={
            <span className={auditRunning || auditTaskId ? "audit-play-running inline-flex rounded-md" : "inline-flex"}>
              <Button onClick={() => void runCampaignAudit()} disabled={auditRunning || !!auditTaskId}>
                ▶ Запустить аудит
              </Button>
            </span>
          }
        />
      </div>

      <nav
        className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/30 px-3 py-2"
        aria-label="Навигация по разделу"
      >
        <Button variant="secondary" size="sm" asChild>
          <Link href="/dashboard">Аккаунты</Link>
        </Button>
        <Button variant="secondary" size="sm" asChild>
          <Link href={`/projects/${encodeURIComponent(effectiveYandexLogin ?? accountKey)}`}>Кампании проекта</Link>
        </Button>
        <Button variant="default" size="sm" type="button" disabled>
          Отчёт кампании
        </Button>
      </nav>

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
              const groupedLayout = rowUsesGroupedLayout(row);
              const locNode = reportRowLocLinks(row, campaignId, effectiveYandexLogin);
              return (
                <tr key={groupedLayout ? `grp:${row.rule_code}:${campaignId}` : row.id} className="border-t">
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
                          {locNode && !groupedLayout && row.rule_code !== RULE_ACTIVE_CAMPAIGN_WITHOUT_ACTIVE_GROUPS ? (
                            <span className="text-xs text-blue-800">
                              Объекты: {locNode}
                            </span>
                          ) : null}
                          <span className="ml-auto text-xs text-muted-foreground">
                            {new Date(row.created_at).toLocaleString("ru-RU")}
                          </span>
                        </div>
                        <p className="mt-1 text-sm text-foreground">{row.impact_ru}</p>
                      </summary>
                      <div className="border-t px-3 py-2">
                        <p className="text-xs font-medium text-muted-foreground">Рекомендация</p>
                        {groupedLayout ? (
                          <>
                            <p className="text-sm">{recommendationText(row, catalogRecommendations)}</p>
                            <GroupedDetailsSection
                              row={row}
                              yandexLogin={effectiveYandexLogin}
                              pageCampaignId={campaignId}
                            />
                          </>
                        ) : (
                          <>
                            <p className="text-sm">{catalogRecommendations[row.rule_code] ?? row.recommendation_ru}</p>
                            <p className="mt-2 text-xs font-medium text-muted-foreground">Детали (снимок аудита)</p>
                            <EvidenceBlock
                              row={row}
                              yandexClientLogin={effectiveYandexLogin}
                              pageCampaignId={campaignId}
                            />
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
