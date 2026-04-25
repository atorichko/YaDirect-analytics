import type { ReactElement, ReactNode } from "react";

import { dnaBannerHref, dnaCampaignHref, dnaGroupHref } from "@/lib/yandex-dna-links";

export type CampaignFinding = {
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

export type DisplayRow = CampaignFinding & {
  mergedSourceRows?: CampaignFinding[];
};

const RULE_ACTIVE_CAMPAIGN_WITHOUT_ACTIVE_GROUPS = "ACTIVE_CAMPAIGN_WITHOUT_ACTIVE_GROUPS";

type HighlightSeg = { text?: string; ok?: boolean };

function SegmentInline({ segments }: { segments: HighlightSeg[] }) {
  if (!segments.length) return null;
  return (
    <p className="mt-1 break-all font-mono text-[11px] leading-relaxed">
      {segments.map((seg, i) => (
        <span
          key={i}
          className={seg.ok === false ? "font-medium text-destructive" : "text-muted-foreground"}
        >
          {seg.text ?? ""}
        </span>
      ))}
    </p>
  );
}

export function AiVerdictPanel({ rows }: { rows: CampaignFinding[] }) {
  const blocks: { reasoning: string; result: string; confidence: string }[] = [];
  for (const r of rows) {
    const v = r.ai_verdict;
    if (!v || typeof v !== "object") continue;
    const o = v as Record<string, unknown>;
    const reasoning = String(o.reasoning_short_ru ?? "").trim();
    const result = String(o.result ?? "").trim();
    const confidence = o.confidence != null ? String(o.confidence) : "";
    if (!reasoning && !result) continue;
    blocks.push({ reasoning, result, confidence });
  }
  if (!blocks.length) return null;
  return (
    <div className="mt-3 rounded-md border border-dashed border-amber-500/50 bg-amber-500/5 px-2 py-2 text-xs dark:bg-amber-950/20">
      <p className="font-medium text-amber-950 dark:text-amber-100">Пояснение ИИ (дополнительная проверка)</p>
      {blocks.map((b, i) => (
        <div key={i} className="mt-1.5 space-y-0.5 text-foreground/90">
          {b.reasoning ? <p className="leading-snug">{b.reasoning}</p> : null}
          <p className="text-muted-foreground">
            {b.result ? <>Итог: {b.result}</> : null}
            {b.confidence ? <> · уверенность: {b.confidence}</> : null}
          </p>
        </div>
      ))}
    </div>
  );
}

const L3_URL_DETAIL_RULES = new Set([
  "INVALID_URL_SYNTAX",
  "EMPTY_OR_TECHNICAL_URL_PARAMS",
  "MISSING_REQUIRED_UTM",
  "INVALID_UTM",
  "UNRESOLVED_PLACEHOLDER_IN_URL",
  "FINAL_URL_HTTP_ERROR",
  "FINAL_URL_DNS_TIMEOUT_CONNECTION_ERROR",
  "FINAL_URL_SSL_TLS_ERROR",
  "HTTP_USED_INSTEAD_OF_HTTPS",
  "REDIRECT_LOOP",
  "REDIRECT_CHAIN_TOO_LONG",
  "FINAL_DOMAIN_DIFFERS_AFTER_REDIRECT",
]);

const L3_URL_HEALTH_DETAIL_RULES = new Set([
  "FINAL_URL_HTTP_ERROR",
  "FINAL_URL_DNS_TIMEOUT_CONNECTION_ERROR",
  "FINAL_URL_SSL_TLS_ERROR",
  "HTTP_USED_INSTEAD_OF_HTTPS",
  "REDIRECT_LOOP",
  "REDIRECT_CHAIN_TOO_LONG",
  "FINAL_DOMAIN_DIFFERS_AFTER_REDIRECT",
]);

/** Rules where multiple findings of the same type in one campaign are shown as a single card. */
export const MERGE_BY_CAMPAIGN_RULES = new Set<string>([
  "ACTIVE_AD_REJECTED_OR_RESTRICTED",
  "ACTIVE_GROUP_WITHOUT_TARGETING",
  "ACTIVE_GROUP_WITHOUT_ACTIVE_ADS",
  "GROUP_ALL_ADS_REJECTED",
  "DUPLICATE_KEYWORDS_IN_GROUP",
  "DUPLICATE_KEYWORDS_WITH_OVERLAP",
  "KEYWORD_CONFLICTS_WITH_GROUP_NEGATIVES",
  "KEYWORD_CONFLICTS_WITH_CAMPAIGN_NEGATIVES",
  "GROUP_KEYWORD_OVERLAP",
  "MISSING_CROSS_NEGATIVES",
  "DUPLICATE_ADS",
  "DUPLICATE_SITELINKS",
  "MISSING_REQUIRED_EXTENSIONS",
  "EXPIRED_DATE_IN_AD_TEXT",
  "PAST_YEAR_IN_TEXT",
  "EXPIRED_DATE_IN_EXTENSIONS",
  "UNRESOLVED_PLACEHOLDER_IN_TEXT",
  "UNRESOLVED_PLACEHOLDER_IN_URL",
  "GEO_TEXT_TARGETING_MISMATCH",
  "CAMPAIGN_SELF_COMPETITION_BY_GEO_AND_SEMANTICS",
  "CAMPAIGN_GEO_OVERLAPS_CAMPAIGN_NEGATIVES",
  "CONVERSION_STRATEGY_WITHOUT_METRIKA",
  "CONVERSION_STRATEGY_WITHOUT_GOAL",
  "CONVERSION_STRATEGY_WITH_UNAVAILABLE_GOAL",
  "CONVERSION_STRATEGY_WITHOUT_LEARNING_DATA",
  "CAMPAIGN_CHRONIC_BUDGET_LIMIT",
  "CAMPAIGN_WITHOUT_METRIKA_COUNTER",
  "CAMPAIGN_WITHOUT_METRIKA_GOALS",
  "INVALID_URL_SYNTAX",
  "FINAL_URL_HTTP_ERROR",
  "FINAL_URL_DNS_TIMEOUT_CONNECTION_ERROR",
  "FINAL_URL_SSL_TLS_ERROR",
  "REDIRECT_LOOP",
  "REDIRECT_CHAIN_TOO_LONG",
  "FINAL_DOMAIN_DIFFERS_AFTER_REDIRECT",
  "HTTP_USED_INSTEAD_OF_HTTPS",
  "BROKEN_SITELINK_URL",
  "MISSING_REQUIRED_UTM",
  "INVALID_UTM",
  "INCONSISTENT_UTM_PATTERN",
  "MAIN_AND_SITELINK_DOMAINS_MISMATCH",
  "EMPTY_OR_TECHNICAL_URL_PARAMS",
]);

function campaignKey(row: CampaignFinding, pageCampaignId: string): string {
  return String(row.campaign_external_id ?? row.evidence?.campaign_id ?? pageCampaignId);
}

function mergeKey(row: CampaignFinding, pageCampaignId: string): string {
  return `${row.rule_code}|${campaignKey(row, pageCampaignId)}`;
}

function maxCreatedAtMs(rows: CampaignFinding[]): number {
  return Math.max(...rows.map((r) => +new Date(r.created_at)));
}

const STATUS_PRIORITY: Record<string, number> = {
  new: 0,
  reopened: 1,
  existing: 2,
  fixed: 3,
  ignored: 4,
  false_positive: 5,
};

function aggregateStatus(rows: CampaignFinding[]): string {
  let best = rows[0].status;
  let bestP = STATUS_PRIORITY[best] ?? 99;
  for (const r of rows.slice(1)) {
    const p = STATUS_PRIORITY[r.status] ?? 99;
    if (p < bestP) {
      best = r.status;
      bestP = p;
    }
  }
  return best;
}

const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  warning: 2,
};

function aggregateSeverity(rows: CampaignFinding[]): string {
  let best = rows[0].severity;
  let bestP = SEVERITY_ORDER[best] ?? 99;
  for (const r of rows.slice(1)) {
    const p = SEVERITY_ORDER[r.severity] ?? 99;
    if (p < bestP) {
      best = r.severity;
      bestP = p;
    }
  }
  return best;
}

function pickLeader(rows: CampaignFinding[]): CampaignFinding {
  return [...rows].sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at))[0];
}

export function buildGroupedCampaignRows(visibleRows: CampaignFinding[], pageCampaignId: string): DisplayRow[] {
  const merged: CampaignFinding[] = [];
  const passThrough: CampaignFinding[] = [];
  for (const row of visibleRows) {
    const scopeAccount = row.evidence && String((row.evidence as Record<string, unknown>).scope ?? "") === "account";
    if (
      row.rule_code === RULE_ACTIVE_CAMPAIGN_WITHOUT_ACTIVE_GROUPS ||
      !MERGE_BY_CAMPAIGN_RULES.has(row.rule_code) ||
      scopeAccount
    ) {
      passThrough.push(row);
      continue;
    }
    merged.push(row);
  }

  const buckets = new Map<string, CampaignFinding[]>();
  for (const row of merged) {
    const k = mergeKey(row, pageCampaignId);
    const arr = buckets.get(k);
    if (arr) arr.push(row);
    else buckets.set(k, [row]);
  }

  const grouped: DisplayRow[] = [];
  for (const rows of buckets.values()) {
    const leader = pickLeader(rows);
    grouped.push({
      ...leader,
      status: aggregateStatus(rows),
      severity: aggregateSeverity(rows),
      mergedSourceRows: [...rows].sort((a, b) => {
        const la = a.issue_location.localeCompare(b.issue_location);
        if (la !== 0) return la;
        return a.id.localeCompare(b.id);
      }),
    });
  }

  const out: DisplayRow[] = [...grouped, ...passThrough];
  out.sort((a, b) => {
    const ta = a.mergedSourceRows ? maxCreatedAtMs(a.mergedSourceRows) : +new Date(a.created_at);
    const tb = b.mergedSourceRows ? maxCreatedAtMs(b.mergedSourceRows) : +new Date(b.created_at);
    return tb - ta;
  });
  return out;
}

export function rowUsesGroupedLayout(row: DisplayRow): boolean {
  return Boolean(row.mergedSourceRows && row.mergedSourceRows.length > 0);
}

export function recommendationText(
  row: DisplayRow,
  catalogRecommendations: Record<string, string>,
): string {
  if (row.rule_code === "ACTIVE_AD_REJECTED_OR_RESTRICTED") {
    return "Исправить объявление по замечаниям модерации.";
  }
  const fromCatalog = catalogRecommendations[row.rule_code];
  if (fromCatalog) return fromCatalog;
  return row.recommendation_ru;
}

function bulletSortKey(row: CampaignFinding): string {
  return [
    row.ad_external_id ?? String(row.evidence?.ad_id ?? ""),
    row.group_external_id ?? String(row.evidence?.group_id ?? ""),
    row.issue_location,
    row.id,
  ].join("|");
}

function formatGenericBullet(row: CampaignFinding): string {
  const ev = row.evidence ?? {};
  const adId = row.ad_external_id ?? ev.ad_id;
  const adTitle = ev.ad_title != null ? String(ev.ad_title).trim() : "";
  if (adId) {
    const idStr = String(adId);
    return adTitle ? `${idStr} - ${adTitle}` : idStr;
  }
  const gid = row.group_external_id ?? ev.group_id;
  const gname = ev.group_name != null ? String(ev.group_name).trim() : "";
  if (gid) {
    const idStr = String(gid);
    return gname ? `${idStr} - ${gname}` : idStr;
  }
  const kw = ev.keyword_text ?? ev.normalized_keyword;
  if (kw) return String(kw);
  const url = ev.checked_url ?? ev.url_value;
  const field = ev.url_field ? String(ev.url_field) : "";
  if (url) {
    const adPart = row.ad_external_id ?? ev.ad_id;
    const bits = [adPart ? String(adPart) : "", field, String(url)].filter(Boolean);
    return bits.join(" — ");
  }
  return row.issue_location;
}

function DnaExternalLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="text-blue-700 underline underline-offset-2">
      {children}
    </a>
  );
}

export function GroupedDetailsSection({
  row,
  yandexLogin,
  pageCampaignId,
}: {
  row: DisplayRow;
  yandexLogin: string | null;
  pageCampaignId: string;
}): ReactElement {
  const rows = row.mergedSourceRows ?? [];
  const sorted = [...rows].sort((a, b) => bulletSortKey(a).localeCompare(bulletSortKey(b)));

  function renderLinkedAdTitle(item: CampaignFinding, ev: Record<string, unknown>): ReactNode {
    const adId = String(item.ad_external_id ?? ev.ad_id ?? "").trim();
    const cid = String(item.campaign_external_id ?? ev.campaign_id ?? pageCampaignId ?? "").trim();
    const gid = String(item.group_external_id ?? ev.group_id ?? "").trim();
    if (!adId) return <>Объявление —</>;
    if (yandexLogin && /^\d+$/.test(cid) && /^\d+$/.test(gid) && /^\d+$/.test(adId)) {
      return (
        <>
          Объявление <DnaExternalLink href={dnaBannerHref(yandexLogin, cid, gid, adId)}>{adId}</DnaExternalLink>
        </>
      );
    }
    return <>Объявление {adId}</>;
  }

  function renderLinkedGroupLabel(groupId: string, campaignIdForLink: string, suffix?: string): ReactNode {
    const cid = campaignIdForLink.trim();
    const gid = groupId.trim();
    if (yandexLogin && /^\d+$/.test(cid) && /^\d+$/.test(gid)) {
      return (
        <>
          Группа <DnaExternalLink href={dnaGroupHref(yandexLogin, cid, gid)}>{gid}</DnaExternalLink>
          {suffix ?? ""}
        </>
      );
    }
    return (
      <>
        Группа {gid}
        {suffix ?? ""}
      </>
    );
  }

  function renderLinkedCampaignId(campaignId: string, display?: string): ReactNode {
    const cid = campaignId.trim();
    const label = (display ?? cid).trim();
    if (yandexLogin && /^\d+$/.test(cid)) {
      return <DnaExternalLink href={dnaCampaignHref(yandexLogin, cid)}>{label}</DnaExternalLink>;
    }
    return <>{label}</>;
  }

  function renderIssueLocationLabel(
    issueLocation: string,
    login: string | null,
    pageCid: string,
    finding: CampaignFinding,
    ev: Record<string, unknown>,
  ): ReactNode {
    const raw = String(issueLocation || "").trim();
    if (!raw.includes(":")) return raw || "—";
    const [scope, idPartRaw] = raw.split(":", 2);
    const idPart = String(idPartRaw || "").trim();
    if (!idPart) return raw;
    if (scope === "campaign") {
      return (
        <>
          Кампания:
          {login && /^\d+$/.test(idPart) ? (
            <DnaExternalLink href={dnaCampaignHref(login, idPart)}>{idPart}</DnaExternalLink>
          ) : (
            idPart
          )}
        </>
      );
    }
    if (scope === "group") {
      const cid = String(finding.campaign_external_id ?? ev.campaign_id ?? pageCid ?? "").trim();
      return (
        <>
          Группа:
          {login && /^\d+$/.test(cid) && /^\d+$/.test(idPart) ? (
            <DnaExternalLink href={dnaGroupHref(login, cid, idPart)}>{idPart}</DnaExternalLink>
          ) : (
            idPart
          )}
        </>
      );
    }
    if (scope === "ad") {
      const cid = String(finding.campaign_external_id ?? ev.campaign_id ?? pageCid ?? "").trim();
      const gid = String(finding.group_external_id ?? ev.group_id ?? "").trim();
      return (
        <>
          Объявление:
          {login && /^\d+$/.test(cid) && /^\d+$/.test(gid) && /^\d+$/.test(idPart) ? (
            <DnaExternalLink href={dnaBannerHref(login, cid, gid, idPart)}>{idPart}</DnaExternalLink>
          ) : (
            idPart
          )}
        </>
      );
    }
    if (scope === "account") return <>Аккаунт:{idPart}</>;
    return raw;
  }

  if (row.rule_code === "ACTIVE_AD_REJECTED_OR_RESTRICTED") {
    const byAd = new Map<
      string,
      { adId: string; adTitle: string; campaignId: string; groupId: string }
    >();
    for (const item of sorted) {
      const adIdRaw = item.ad_external_id ?? item.evidence?.ad_id;
      if (!adIdRaw) continue;
      const adId = String(adIdRaw);
      const adTitleRaw = item.evidence?.ad_title;
      const adTitle = String(adTitleRaw ?? "").trim() || "Название объявления недоступно";
      if (!byAd.has(adId)) {
        byAd.set(adId, {
          adId,
          adTitle,
          campaignId: String(item.campaign_external_id ?? pageCampaignId ?? ""),
          groupId: String(item.group_external_id ?? ""),
        });
      }
    }
    const list = Array.from(byAd.values()).sort((a, b) => a.adId.localeCompare(b.adId));
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <div className="text-sm text-foreground">
          <p>Объявления, не прошедшие модерацию:</p>
          <ul className="mt-1 list-inside list-disc">
            {list.map((item) => (
              <li key={item.adId}>
                {yandexLogin &&
                /^\d+$/.test(item.campaignId) &&
                /^\d+$/.test(item.groupId) &&
                /^\d+$/.test(item.adId) ? (
                  <>
                    <DnaExternalLink href={dnaBannerHref(yandexLogin, item.campaignId, item.groupId, item.adId)}>
                      {item.adId}
                    </DnaExternalLink>
                    {" — "}
                    {item.adTitle}
                  </>
                ) : (
                  <>
                    {item.adId} — {item.adTitle}
                  </>
                )}
              </li>
            ))}
          </ul>
        </div>
      </>
    );
  }

  if (row.rule_code === "ACTIVE_GROUP_WITHOUT_TARGETING") {
    const byGroup = new Map<string, { groupId: string; groupName: string }>();
    for (const item of sorted) {
      const gidRaw = item.group_external_id ?? item.evidence?.group_id;
      if (!gidRaw) continue;
      const groupId = String(gidRaw);
      const groupNameRaw = item.evidence?.group_name;
      const groupName = String(groupNameRaw ?? "").trim() || "Название группы недоступно";
      if (!byGroup.has(groupId)) byGroup.set(groupId, { groupId, groupName });
    }
    const list = Array.from(byGroup.values()).sort((a, b) => a.groupId.localeCompare(b.groupId));
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <div className="text-sm text-foreground">
          <p>Группы без активного таргетинга:</p>
          <ul className="mt-1 list-inside list-disc">
            {list.map((item) => (
              <li key={item.groupId}>
                {renderLinkedGroupLabel(item.groupId, pageCampaignId, ` — ${item.groupName}`)}
              </li>
            ))}
          </ul>
        </div>
      </>
    );
  }

  if (row.rule_code === "DUPLICATE_KEYWORDS_IN_GROUP") {
    type Conflict = { keyword_id: string; phrase: string; minus_tokens: string[] };
    const byGroup = new Map<
      string,
      { groupId: string; groupName: string; campaignId: string; duplicates: string[]; conflicts: Conflict[] }
    >();
    for (const item of sorted) {
      const gidRaw = item.group_external_id ?? item.evidence?.group_id;
      if (!gidRaw) continue;
      const groupId = String(gidRaw);
      const groupName = String(item.evidence?.group_name ?? "").trim() || "—";
      const phrases = (item.evidence?.duplicate_phrases as string[] | undefined) ??
        (item.evidence?.keywords as string[] | undefined) ?? [];
      const rawConflicts = (item.evidence?.minus_word_conflicts as Conflict[] | undefined) ?? [];
      const cur = byGroup.get(groupId) ?? {
        groupId,
        groupName,
        campaignId: String(item.campaign_external_id ?? item.evidence?.campaign_id ?? pageCampaignId ?? ""),
        duplicates: [] as string[],
        conflicts: [] as Conflict[],
      };
      cur.duplicates.push(...phrases);
      cur.conflicts.push(...rawConflicts);
      byGroup.set(groupId, cur);
    }
    const list = Array.from(byGroup.values()).sort((a, b) => a.groupId.localeCompare(b.groupId));
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <div className="space-y-3 text-sm text-foreground">
          {list.map((g) => {
            const dupUnique = [...new Set(g.duplicates)].sort();
            const confById = new Map<string, Conflict>();
            for (const c of g.conflicts) {
              if (!confById.has(c.keyword_id)) confById.set(c.keyword_id, c);
            }
            const confList = [...confById.values()].sort((a, b) => a.keyword_id.localeCompare(b.keyword_id));
            return (
              <div key={g.groupId}>
                <p className="font-medium">
                  {renderLinkedGroupLabel(g.groupId, g.campaignId || pageCampaignId, ` — ${g.groupName}`)}
                </p>
                {dupUnique.length > 0 && (
                  <>
                    <p className="mt-1 text-muted-foreground">Дубли ключевых фраз:</p>
                    <ul className="mt-0.5 list-inside list-disc">
                      {dupUnique.map((p) => (
                        <li key={p}>«{p}»</li>
                      ))}
                    </ul>
                  </>
                )}
                {confList.length > 0 && (
                  <>
                    <p className="mt-1 text-muted-foreground">Конфликт ключа с минус-словом группы:</p>
                    <ul className="mt-0.5 list-inside list-disc">
                      {confList.map((c) => (
                        <li key={c.keyword_id}>
                          «{c.phrase}» — минус-слова: {c.minus_tokens.join(", ")}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </>
    );
  }

  if (row.rule_code === "GEO_TEXT_TARGETING_MISMATCH") {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <div className="mt-1 space-y-3 text-sm text-foreground">
          {sorted.map((r) => {
            const ev = r.evidence ?? {};
            const title = String(ev.ad_title ?? "").trim();
            const detail = String(ev.conflict_detail_ru ?? "").trim();
            const targeting = String(ev.campaign_targeting_summary_ru ?? "").trim();
            const mentioned = String(ev.mentioned_city_label_ru ?? "").trim();
            return (
              <div key={r.id} className="rounded-md border border-border/60 bg-muted/20 px-2 py-2">
                <p className="font-medium">
                  {renderLinkedAdTitle(r, ev)}
                  {title ? ` — ${title}` : ""}
                </p>
                {mentioned ? (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Город/регион в тексте (детектор): <span className="text-destructive">{mentioned}</span>
                  </p>
                ) : null}
                {targeting ? (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Геотаргетинг кампании: <span className="font-medium text-foreground">{targeting}</span>
                  </p>
                ) : null}
                {detail ? <p className="mt-1.5 text-sm leading-snug text-foreground">{detail}</p> : null}
              </div>
            );
          })}
        </div>
        <AiVerdictPanel rows={sorted} />
      </>
    );
  }

  if (row.rule_code === "CAMPAIGN_SELF_COMPETITION_BY_GEO_AND_SEMANTICS") {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <ul className="mt-1 list-inside list-disc space-y-2 text-sm text-foreground">
          {sorted.map((r) => {
            const ev = r.evidence ?? {};
            const label = String(ev.campaign_pair_label_ru ?? "").trim();
            const lname = String(ev.left_campaign_name ?? "").trim();
            const rname = String(ev.right_campaign_name ?? "").trim();
            const lid = String(ev.left_campaign_id ?? "");
            const rid = String(ev.right_campaign_id ?? "");
            const pairLine =
              label ||
              (lname && rname
                ? `Кампании «${lname}» (${lid}) и «${rname}» (${rid})`
                : lid && rid
                  ? `Кампании ${lid} ↔ ${rid}`
                  : "Пара кампаний (см. снимок аудита)");
            const geo = (ev.overlapping_geo_labels as string[] | undefined) ?? [];
            const sem = (ev.semantic_overlap_examples as string[] | undefined) ?? [];
            const gids = (ev.geo_overlap as string[] | undefined) ?? [];
            return (
              <li key={r.id}>
                {label ? (
                  <p className="font-medium">{label}</p>
                ) : lname && rname && lid && rid ? (
                  <p className="font-medium">
                    Кампании «{lname}» ({renderLinkedCampaignId(lid)}) и «{rname}» ({renderLinkedCampaignId(rid)})
                  </p>
                ) : lid && rid ? (
                  <p className="font-medium">
                    Кампании {renderLinkedCampaignId(lid)} ↔ {renderLinkedCampaignId(rid)}
                  </p>
                ) : (
                  <p className="font-medium">{pairLine}</p>
                )}
                {gids.length > 0 ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">Пересечение гео (id/метки): {gids.join(", ")}</p>
                ) : null}
                {geo.length > 0 ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">Пересечение гео: {geo.join(", ")}</p>
                ) : null}
                {sem.length > 0 ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">Примеры общей семантики: {sem.join(", ")}</p>
                ) : null}
                {ev.detail_summary_ru ? (
                  <p className="mt-0.5 text-xs text-foreground/90">{String(ev.detail_summary_ru)}</p>
                ) : null}
              </li>
            );
          })}
        </ul>
        <AiVerdictPanel rows={sorted} />
      </>
    );
  }

  if (row.rule_code === "GROUP_KEYWORD_OVERLAP") {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <div className="space-y-3 text-sm text-foreground">
          {sorted.map((r) => {
            const ev = r.evidence ?? {};
            const common = (ev.overlap_keywords as string[] | undefined) ?? [];
            const cnt = typeof ev.overlap_keywords_count === "number" ? ev.overlap_keywords_count : common.length;
            const leftS = (ev.overlap_phrases_left_sample as string[] | undefined) ?? [];
            const rightS = (ev.overlap_phrases_right_sample as string[] | undefined) ?? [];
            const summary = String(ev.detail_summary_ru ?? "").trim();
            const expl = String(ev.issue_explanation_ru ?? "").trim();
            const lg = String(ev.left_group_name ?? ev.left_group_id ?? "");
            const rg = String(ev.right_group_name ?? ev.right_group_id ?? "");
            const cid = String(ev.campaign_id ?? "");
            return (
              <div key={r.id} className="rounded-md border border-border/50 px-2 py-2">
                <p className="font-medium">
                  Кампания {cid ? renderLinkedCampaignId(cid) : "—"}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Группа А:{" "}
                  {yandexLogin &&
                  /^\d+$/.test((cid || pageCampaignId).trim()) &&
                  /^\d+$/.test(String(ev.left_group_id ?? "").trim()) ? (
                    <DnaExternalLink
                      href={dnaGroupHref(yandexLogin, (cid || pageCampaignId).trim(), String(ev.left_group_id ?? "").trim())}
                    >
                      {String(ev.left_group_id ?? "")}
                    </DnaExternalLink>
                  ) : (
                    String(ev.left_group_id ?? "")
                  )}
                  {lg ? ` — «${lg}»` : ""}
                </p>
                <p className="text-xs text-muted-foreground">
                  Группа Б:{" "}
                  {yandexLogin &&
                  /^\d+$/.test((cid || pageCampaignId).trim()) &&
                  /^\d+$/.test(String(ev.right_group_id ?? "").trim()) ? (
                    <DnaExternalLink
                      href={dnaGroupHref(
                        yandexLogin,
                        (cid || pageCampaignId).trim(),
                        String(ev.right_group_id ?? "").trim(),
                      )}
                    >
                      {String(ev.right_group_id ?? "")}
                    </DnaExternalLink>
                  ) : (
                    String(ev.right_group_id ?? "")
                  )}
                  {rg ? ` — «${rg}»` : ""}
                </p>
                {summary ? <p className="mt-1 text-xs text-muted-foreground">{summary}</p> : null}
                {expl ? <p className="mt-1 text-xs leading-snug text-foreground/95">{expl}</p> : null}
                {common.length > 0 ? (
                  <p className="mt-1 text-xs">
                    Совпадающие нормализованные ключи ({cnt}): {common.join(", ")}
                  </p>
                ) : null}
                {leftS.length > 0 ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">Примеры фраз в группе А: {leftS.join("; ")}</p>
                ) : null}
                {rightS.length > 0 ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">Примеры фраз в группе Б: {rightS.join("; ")}</p>
                ) : null}
              </div>
            );
          })}
        </div>
        <AiVerdictPanel rows={sorted} />
      </>
    );
  }

  if (row.rule_code === "KEYWORD_CONFLICTS_WITH_GROUP_NEGATIVES" || row.rule_code === "KEYWORD_CONFLICTS_WITH_CAMPAIGN_NEGATIVES") {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <ul className="mt-1 list-inside list-disc space-y-2 text-sm text-foreground">
          {sorted.map((r) => {
            const ev = r.evidence ?? {};
            const phrase = String(ev.keyword_phrase ?? ev.keyword_text ?? "");
            const minus = String(ev.conflicting_minus_word ?? ev.conflicting_negative ?? "");
            return (
              <li key={r.id}>
                {r.ad_external_id || ev.ad_id ? (
                  <p className="font-medium">{renderLinkedAdTitle(r, ev)}</p>
                ) : null}
                <p className="mt-0.5 text-xs">
                  Ключевая фраза: <span className="font-medium">«{phrase}»</span>
                </p>
                <p className="text-xs">
                  Конфликтующее минус-слово: <span className="text-destructive">{minus}</span>
                </p>
              </li>
            );
          })}
        </ul>
      </>
    );
  }

  if (row.rule_code === "DUPLICATE_KEYWORDS_WITH_OVERLAP") {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <ul className="mt-1 list-inside list-disc text-sm text-foreground">
          {sorted.map((r) => {
            const ev = r.evidence ?? {};
            const kind = String(ev.overlap_kind ?? "");
            const lk = String(ev.left_keyword ?? "");
            const rk = String(ev.right_keyword ?? "");
            const lg = String(ev.left_group_id ?? "");
            const rg = String(ev.right_group_id ?? "");
            const lc = String(ev.left_campaign_id ?? "");
            const rc = String(ev.right_campaign_id ?? "");
            let prefix: ReactNode = "";
            if (kind === "cross_campaign") {
              prefix =
                yandexLogin && /^\d+$/.test(lc) && /^\d+$/.test(rc) ? (
                  <>
                    Кампании {renderLinkedCampaignId(lc)} ↔ {renderLinkedCampaignId(rc)}:{" "}
                  </>
                ) : (
                  `Кампании ${lc} ↔ ${rc}: `
                );
            } else if (kind === "cross_group") {
              const ccmp = String(
                ev.left_campaign_id ?? ev.right_campaign_id ?? r.campaign_external_id ?? pageCampaignId ?? "",
              );
              prefix =
                yandexLogin && /^\d+$/.test(ccmp) && /^\d+$/.test(lg) && /^\d+$/.test(rg) ? (
                  <>
                    Группы{" "}
                    <DnaExternalLink href={dnaGroupHref(yandexLogin, ccmp, lg)}>{lg}</DnaExternalLink> ↔{" "}
                    <DnaExternalLink href={dnaGroupHref(yandexLogin, ccmp, rg)}>{rg}</DnaExternalLink>:{" "}
                  </>
                ) : (
                  `Группы ${lg} ↔ ${rg}: `
                );
            } else if (lg) {
              const ccmp = String(
                ev.left_campaign_id ?? ev.right_campaign_id ?? r.campaign_external_id ?? pageCampaignId ?? "",
              );
              prefix =
                yandexLogin && /^\d+$/.test(ccmp) && /^\d+$/.test(lg) ? (
                  <>
                    <DnaExternalLink href={dnaGroupHref(yandexLogin, ccmp, lg)}>{lg}</DnaExternalLink>:{" "}
                  </>
                ) : (
                  `Группа ${lg}: `
                );
            }
            return (
              <li key={r.id}>
                {prefix}«{lk}» и «{rk}»
              </li>
            );
          })}
        </ul>
        <AiVerdictPanel rows={sorted} />
      </>
    );
  }

  if (row.rule_code === "MISSING_CROSS_NEGATIVES") {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <div className="space-y-3 text-sm text-foreground">
          {sorted.map((r) => {
            const ev = r.evidence ?? {};
            const gid = String(ev.group_id ?? "");
            const gname = String(ev.group_name ?? "").trim();
            const missing = (ev.missing_negative_tokens as string[] | undefined) ?? [];
            const examples =
              (ev.cross_minus_phrase_examples as Array<{ label?: string; phrase?: string; shared_token?: string }> | undefined) ??
              [];
            const ccmp = String(r.campaign_external_id ?? pageCampaignId ?? "");
            return (
              <div key={r.id} className="rounded-md border border-border/50 px-2 py-2">
                <p className="font-medium">
                  Группа{" "}
                  {yandexLogin && /^\d+$/.test(ccmp.trim()) && /^\d+$/.test(gid.trim()) ? (
                    <DnaExternalLink href={dnaGroupHref(yandexLogin, ccmp.trim(), gid.trim())}>{gid}</DnaExternalLink>
                  ) : (
                    gid
                  )}
                  {gname ? ` — «${gname}»` : ""}
                </p>
                {missing.length > 0 ? (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Не хватает кросс-минусовки по токенам: {missing.join(", ")}
                  </p>
                ) : null}
                {examples.length > 0 ? (
                  <>
                    <p className="mt-2 text-xs font-medium text-muted-foreground">Примеры пересечений с другими группами</p>
                    <ul className="mt-0.5 list-inside list-disc space-y-1 text-xs">
                      {examples.map((ex, i) => (
                        <li key={`${r.id}-ex-${i}`}>
                          <span className="text-muted-foreground">{String(ex.label ?? "пример")}: </span>«
                          {String(ex.phrase ?? "")}» — общий токен{" "}
                          <span className="text-destructive">{String(ex.shared_token ?? "")}</span>
                        </li>
                      ))}
                    </ul>
                  </>
                ) : null}
              </div>
            );
          })}
        </div>
      </>
    );
  }

  if (row.rule_code === "DUPLICATE_ADS") {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <div className="space-y-3 text-sm text-foreground">
          {sorted.map((item) => {
            const ev = item.evidence ?? {};
            const aids = (ev.ad_ids as string[] | undefined) ?? [];
            const sums = (ev.ads_image_summaries as Array<{ ad_id?: string; caption_ru?: string }> | undefined) ?? [];
            const sig = ev.duplicate_signature_summary as Record<string, unknown> | undefined;
            return (
              <div key={item.id}>
                <p className="text-muted-foreground">
                  Объявления:{" "}
                  {aids.map((aid, idx) => {
                    const cid = String(item.campaign_external_id ?? ev.campaign_id ?? pageCampaignId ?? "").trim();
                    const gid = String(item.group_external_id ?? ev.group_id ?? "").trim();
                    const canLink =
                      Boolean(yandexLogin) && /^\d+$/.test(cid) && /^\d+$/.test(gid) && /^\d+$/.test(String(aid).trim());
                    return (
                      <span key={`${item.id}-ad-${aid}`}>
                        {idx > 0 ? ", " : null}
                        {canLink ? (
                          <DnaExternalLink href={dnaBannerHref(String(yandexLogin), cid, gid, String(aid).trim())}>
                            {String(aid).trim()}
                          </DnaExternalLink>
                        ) : (
                          String(aid).trim()
                        )}
                      </span>
                    );
                  })}
                  {sig?.title != null || sig?.url != null ? (
                    <span className="block text-xs">
                      {String(sig.title ?? "")} · {String(sig.url ?? "")}
                    </span>
                  ) : null}
                </p>
                {sums.length > 0 ? (
                  <ul className="mt-1 list-inside list-disc">
                    {sums.map((s, idx) => {
                      const sid = String(s.ad_id ?? "").trim();
                      const cid = String(item.campaign_external_id ?? ev.campaign_id ?? pageCampaignId ?? "").trim();
                      const gid = String(item.group_external_id ?? ev.group_id ?? "").trim();
                      const canLink =
                        Boolean(yandexLogin) && sid && /^\d+$/.test(sid) && /^\d+$/.test(cid) && /^\d+$/.test(gid);
                      return (
                        <li key={`${item.id}-${s.ad_id ?? idx}`}>
                          {canLink ? (
                            <DnaExternalLink href={dnaBannerHref(String(yandexLogin), cid, gid, sid)}>{sid}</DnaExternalLink>
                          ) : (
                            sid
                          )}
                          : {String(s.caption_ru ?? "")}
                        </li>
                      );
                    })}
                  </ul>
                ) : null}
              </div>
            );
          })}
        </div>
      </>
    );
  }

  if (L3_URL_DETAIL_RULES.has(row.rule_code)) {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <div className="space-y-4 text-sm text-foreground">
          {sorted.map((item) => {
            const ev = item.evidence ?? {};
            const url = String(ev.checked_url ?? ev.display_url_full ?? ev.url_value ?? "");
            const field = String(ev.url_field ?? "");
            const sid = ev.sitelink_id != null ? String(ev.sitelink_id) : "";
            const expl = String(ev.issue_explanation_ru ?? "").trim();
            const code = row.rule_code;
            const isUrlHealthRule = L3_URL_HEALTH_DETAIL_RULES.has(code);
            let segments: HighlightSeg[] = [];
            if (code === "INVALID_URL_SYNTAX") {
              segments =
                (ev.full_url_highlight_segments as HighlightSeg[]) ?? (ev.url_value_segments as HighlightSeg[]) ?? [];
            } else if (code === "EMPTY_OR_TECHNICAL_URL_PARAMS") {
              segments = (ev.query_highlight_segments as HighlightSeg[]) ?? [];
            } else if (code === "MISSING_REQUIRED_UTM" || code === "INVALID_UTM") {
              segments = (ev.url_query_highlight_segments as HighlightSeg[]) ?? [];
            } else if (code === "UNRESOLVED_PLACEHOLDER_IN_URL") {
              segments = (ev.url_highlight_segments as HighlightSeg[]) ?? [];
            }
            const qIdx = url.indexOf("?");
            const showSplitQuery =
              !isUrlHealthRule && code === "EMPTY_OR_TECHNICAL_URL_PARAMS" && qIdx > 0 && segments.length > 0;
            const checkedUrl = String(ev.checked_url ?? ev.display_url_full ?? ev.url_value ?? url ?? "");
            const finalUrl = String(ev.final_url ?? "").trim();
            const flowRu = String(ev.redirect_chain_flow_ru ?? "").trim();
            const domainShiftRu = String(ev.domain_shift_ru ?? "").trim();
            return (
              <div key={item.id} className="rounded-md border border-border/50 px-2 py-2">
                <p className="font-medium">{renderLinkedAdTitle(item, ev)}</p>
                {field ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Поле: {field}
                    {sid ? ` · быстрая ссылка ID ${sid}` : ""}
                  </p>
                ) : null}
                {isUrlHealthRule ? (
                  <>
                    <p className="mt-1 text-xs font-medium text-muted-foreground">Ссылка, на которой сработала проверка</p>
                    <p className="break-all font-mono text-[11px] text-destructive">{checkedUrl || "—"}</p>
                    {finalUrl && finalUrl !== checkedUrl ? (
                      <>
                        <p className="mt-2 text-xs font-medium text-muted-foreground">Финальный URL после редиректов</p>
                        <p className="break-all font-mono text-[11px] text-muted-foreground">{finalUrl}</p>
                      </>
                    ) : null}
                    {code === "FINAL_URL_HTTP_ERROR" && ev.status_code != null ? (
                      <p className="mt-1 text-xs">
                        HTTP-код ответа:{" "}
                        <span className="font-medium text-destructive">{String(ev.status_code)}</span>
                      </p>
                    ) : null}
                    {code === "FINAL_URL_DNS_TIMEOUT_CONNECTION_ERROR" && ev.network_error ? (
                      <p className="mt-1 text-xs text-destructive">Сеть/DNS: {String(ev.network_error)}</p>
                    ) : null}
                    {code === "FINAL_URL_SSL_TLS_ERROR" && ev.ssl_error ? (
                      <p className="mt-1 text-xs text-destructive">SSL/TLS: {String(ev.ssl_error)}</p>
                    ) : null}
                    {code === "HTTP_USED_INSTEAD_OF_HTTPS" && ev.https_available != null ? (
                      <p className="mt-1 text-xs text-muted-foreground">
                        HTTPS доступен (по проверке): {String(ev.https_available)}
                      </p>
                    ) : null}
                    {(code === "REDIRECT_LOOP" || code === "REDIRECT_CHAIN_TOO_LONG") && ev.redirect_hops != null ? (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Число переходов (редиректов): {String(ev.redirect_hops)}
                        {ev.max_redirect_hops != null ? ` · лимит правила: ${String(ev.max_redirect_hops)}` : ""}
                      </p>
                    ) : null}
                    {flowRu ? (
                      <p className="mt-1 text-xs leading-snug text-foreground/90">
                        Цепочка: {flowRu}
                      </p>
                    ) : null}
                    {code === "FINAL_DOMAIN_DIFFERS_AFTER_REDIRECT" ? (
                      <p className="mt-1 text-xs leading-snug text-foreground/90">
                        {domainShiftRu ||
                          (ev.source_domain || ev.final_domain
                            ? `Домен в ссылке: «${String(ev.source_domain ?? "")}» → после редиректов: «${String(
                                ev.final_domain ?? "",
                              )}».`
                            : "")}
                      </p>
                    ) : null}
                  </>
                ) : (
                  <>
                    <p className="mt-1 text-xs font-medium text-muted-foreground">Ссылка</p>
                    {showSplitQuery ? (
                      <>
                        <p className="break-all font-mono text-[11px] text-muted-foreground">{url.slice(0, qIdx + 1)}</p>
                        <SegmentInline segments={segments} />
                      </>
                    ) : segments.length > 0 ? (
                      <SegmentInline segments={segments} />
                    ) : url ? (
                      <p className="break-all font-mono text-[11px] text-muted-foreground">{url}</p>
                    ) : (
                      <p className="text-xs text-muted-foreground">URL в снимке отсутствует.</p>
                    )}
                  </>
                )}
                {code === "INVALID_UTM" && Array.isArray(ev.utm_issue_details) ? (
                  <ul className="mt-2 list-inside list-disc text-[11px] text-muted-foreground">
                    {(ev.utm_issue_details as { code?: string; issue?: string }[]).map((d, i) => (
                      <li key={i}>
                        <span className="text-destructive">{String(d.code ?? "")}</span>
                        {d.issue ? `: ${String(d.issue)}` : ""}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {code === "MISSING_REQUIRED_UTM" && Array.isArray(ev.missing_utm_params) ? (
                  <p className="mt-2 text-xs text-destructive">
                    Отсутствуют обязательные UTM: {(ev.missing_utm_params as string[]).join(", ")}
                  </p>
                ) : null}
                {code === "INVALID_URL_SYNTAX" && Array.isArray(ev.url_syntax_issues) ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    {(ev.url_syntax_issues as string[]).join("; ")}
                  </p>
                ) : null}
                {expl ? <p className="mt-2 text-xs leading-snug text-foreground/90">{expl}</p> : null}
              </div>
            );
          })}
        </div>
        <AiVerdictPanel rows={sorted} />
      </>
    );
  }

  if (row.rule_code === "MAIN_AND_SITELINK_DOMAINS_MISMATCH") {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <div className="space-y-4 text-sm text-foreground">
          {sorted.map((item) => {
            const ev = item.evidence ?? {};
            const mainUrl = String(ev.main_url ?? ev.main_url_display ?? "");
            const rows =
              (ev.sitelink_urls as { url?: string; sitelink_id?: string; matches_main_domain?: boolean }[]) ?? [];
            const note = String(ev.urls_comparison_note_ru ?? "").trim();
            return (
              <div key={item.id} className="rounded-md border border-border/50 px-2 py-2">
                <p className="font-medium">{renderLinkedAdTitle(item, ev)}</p>
                {note ? <p className="mt-1 text-xs text-muted-foreground">{note}</p> : null}
                <p className="mt-2 text-xs font-medium text-muted-foreground">Основная ссылка объявления</p>
                <p className="break-all font-mono text-[11px]">{mainUrl || "—"}</p>
                <p className="mt-2 text-xs font-medium text-muted-foreground">Быстрые ссылки</p>
                <ul className="mt-0.5 list-inside list-disc space-y-1 break-all font-mono text-[11px]">
                  {rows.map((sr, i) => (
                    <li key={i} className={sr.matches_main_domain === false ? "text-destructive" : ""}>
                      {sr.sitelink_id != null ? `ID ${String(sr.sitelink_id)} — ` : null}
                      {String(sr.url ?? "")}
                      {sr.matches_main_domain === false ? " (домен отличается от основной ссылки)" : ""}
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
        <AiVerdictPanel rows={sorted} />
      </>
    );
  }

  if (row.rule_code === "INCONSISTENT_UTM_PATTERN") {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <div className="space-y-3 text-sm text-foreground">
          {sorted.map((item) => {
            const ev = item.evidence ?? {};
            if (String(ev.scope ?? "") === "account") return null;
            const conflicts = ev.utm_conflicts as Record<string, string[]> | undefined;
            const expl = String(ev.issue_explanation_ru ?? "").trim();
            if (!conflicts || !Object.keys(conflicts).length) return null;
            return (
              <div key={item.id} className="rounded-md border border-border/50 px-2 py-2">
                <p className="font-medium">{renderLinkedAdTitle(item, ev)}</p>
                <ul className="mt-1 list-inside list-disc text-xs">
                  {Object.entries(conflicts).map(([k, vals]) => (
                    <li key={k}>
                      <span className="font-medium">{k}</span>: {vals.join(" · ")}
                    </li>
                  ))}
                </ul>
                {expl ? <p className="mt-2 text-xs leading-snug text-muted-foreground">{expl}</p> : null}
              </div>
            );
          })}
        </div>
        <AiVerdictPanel rows={sorted} />
      </>
    );
  }

  if (row.rule_code === "EXPIRED_DATE_IN_AD_TEXT") {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <ul className="mt-1 space-y-2 text-sm text-foreground">
          {sorted.map((item) => {
            const ev = item.evidence ?? {};
            const matched = String(ev.matched_date_text ?? "");
            const today = String(ev.audit_reference_today_ru ?? ev.audit_reference_today ?? "");
            return (
              <li key={item.id} className="rounded-md border border-border/50 px-2 py-2">
                <p className="font-medium">{renderLinkedAdTitle(item, ev)}</p>
                <p className="mt-1 text-xs">
                  Дата в тексте (как указано):{" "}
                  <span className="font-semibold text-destructive">«{matched}»</span>
                </p>
                {today ? <p className="mt-1 text-xs text-muted-foreground">{today}</p> : null}
              </li>
            );
          })}
        </ul>
      </>
    );
  }

  if (row.rule_code === "EXPIRED_DATE_IN_EXTENSIONS") {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <ul className="mt-1 space-y-2 text-sm text-foreground">
          {sorted.map((item) => {
            const ev = item.evidence ?? {};
            const ext = String(ev.extension_type ?? "");
            const matched = String(ev.matched_date_text ?? "");
            const today = String(ev.audit_reference_today_ru ?? ev.audit_reference_today ?? "");
            const st = String(ev.sitelink_title ?? "").trim();
            const ct = String(ev.callout_text ?? "").trim();
            return (
              <li key={item.id} className="rounded-md border border-border/50 px-2 py-2">
                <p className="font-medium">{renderLinkedAdTitle(item, ev)}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Расширение: {ext || "—"}
                  {st ? ` — быстрая ссылка «${st}»` : ""}
                  {ct ? ` — уточнение «${ct}»` : ""}
                </p>
                <p className="mt-1 text-xs">
                  Дата в тексте (как указано):{" "}
                  <span className="font-semibold text-destructive">«{matched}»</span>
                </p>
                {today ? <p className="mt-1 text-xs text-muted-foreground">{today}</p> : null}
              </li>
            );
          })}
        </ul>
      </>
    );
  }

  if (row.rule_code === "PAST_YEAR_IN_TEXT" || row.rule_code === "UNRESOLVED_PLACEHOLDER_IN_TEXT") {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <div className="space-y-3 text-sm text-foreground">
          {sorted.map((item) => {
            const ev = item.evidence ?? {};
            const raw = String(ev.ad_text_for_audit ?? "");
            const segments = (ev.text_highlight_segments as HighlightSeg[]) ?? [];
            return (
              <div key={item.id} className="rounded-md border border-border/50 px-2 py-2">
                <p className="font-medium">{renderLinkedAdTitle(item, ev)}</p>
                <p className="mt-1 text-xs text-muted-foreground">Текст объявления (заголовок и текст)</p>
                {segments.length > 0 ? (
                  <SegmentInline segments={segments} />
                ) : (
                  <p className="mt-1 break-words font-mono text-[11px] text-muted-foreground">{raw}</p>
                )}
              </div>
            );
          })}
        </div>
      </>
    );
  }

  if (row.rule_code === "BROKEN_SITELINK_URL") {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <div className="space-y-3 text-sm text-foreground">
          {sorted.map((item) => {
            const ev = item.evidence ?? {};
            const urls =
              (ev.broken_sitelink_urls as Array<{ sitelink_id?: string; url?: string }> | undefined) ?? [];
            const ids = (ev.broken_sitelinks as string[] | undefined) ?? [];
            return (
              <div key={item.id}>
                <p className="font-medium">{renderLinkedAdTitle(item, ev)}</p>
                {urls.length > 0 ? (
                  <ul className="mt-1 list-inside list-disc break-all font-mono text-xs">
                    {urls.map((u, idx) => (
                      <li key={`${item.id}-sl-${idx}`}>
                        {u.sitelink_id != null ? (
                          <span className="text-muted-foreground">Быстрая ссылка ID {String(u.sitelink_id)} — </span>
                        ) : null}
                        <span className="text-destructive">{String(u.url ?? "—")}</span>
                      </li>
                    ))}
                  </ul>
                ) : ids.length > 0 ? (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Битые быстрые ссылки (только ID в снимке): {ids.join(", ")}
                  </p>
                ) : (
                  <p className="mt-1 text-xs text-muted-foreground">URL быстрых ссылок в данных не переданы.</p>
                )}
              </div>
            );
          })}
        </div>
      </>
    );
  }

  if (
    row.rule_code === "CAMPAIGN_CHRONIC_BUDGET_LIMIT" ||
    row.rule_code === "CONVERSION_STRATEGY_WITHOUT_LEARNING_DATA" ||
    row.rule_code === "CONVERSION_STRATEGY_WITH_UNAVAILABLE_GOAL"
  ) {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <div className="space-y-3 text-sm text-foreground">
          {sorted.map((r) => {
            const ev = r.evidence ?? {};
            const logic = String(ev.check_logic_ru ?? "").trim();
            const cid = String(r.campaign_external_id ?? ev.campaign_id ?? "");
            return (
              <div key={r.id} className="rounded-md border border-border/50 px-2 py-2">
                {cid ? (
                  <p className="font-medium">
                    Кампания {renderLinkedCampaignId(cid)}
                  </p>
                ) : null}
                {logic ? <p className="mt-1 text-xs leading-snug text-muted-foreground">{logic}</p> : null}
                {row.rule_code === "CAMPAIGN_CHRONIC_BUDGET_LIMIT" ? (
                  <ul className="mt-1 list-inside list-disc text-xs text-muted-foreground">
                    <li>
                      Дней с ограничением по бюджету (stats.budget_limited_days):{" "}
                      <span className="font-medium text-foreground">{String(ev.budget_limited_days ?? "—")}</span>
                    </li>
                    <li>
                      Порог правила (budget_limited_days_threshold):{" "}
                      <span className="font-medium text-foreground">{String(ev.threshold_days ?? "—")}</span>
                    </li>
                    {ev.analysis_period_days != null ? (
                      <li>Окно анализа (дней): {String(ev.analysis_period_days)}</li>
                    ) : null}
                  </ul>
                ) : null}
                {row.rule_code === "CONVERSION_STRATEGY_WITHOUT_LEARNING_DATA" ? (
                  <ul className="mt-1 list-inside list-disc text-xs text-muted-foreground">
                    <li>
                      Конверсии за период (stats.conversions):{" "}
                      <span className="font-medium text-foreground">{String(ev.conversions ?? "—")}</span>
                    </li>
                    <li>
                      Минимум для обучения (required_min_conversions):{" "}
                      <span className="font-medium text-foreground">{String(ev.required_min_conversions ?? "—")}</span>
                    </li>
                    {ev.analysis_period_days != null ? (
                      <li>Окно анализа (дней): {String(ev.analysis_period_days)}</li>
                    ) : null}
                  </ul>
                ) : null}
                {row.rule_code === "CONVERSION_STRATEGY_WITH_UNAVAILABLE_GOAL" ? (
                  <ul className="mt-1 list-inside list-disc text-xs text-muted-foreground">
                    {(Array.isArray(ev.problem_goals) ? (ev.problem_goals as Record<string, unknown>[]) : []).map(
                      (pg, i) => (
                        <li key={`${r.id}-pg-${i}`}>
                          Цель {String(pg.goal_id ?? "")}: {String(pg.reason ?? pg.status ?? pg.access ?? "—")}
                        </li>
                      ),
                    )}
                  </ul>
                ) : null}
              </div>
            );
          })}
        </div>
      </>
    );
  }

  if (row.rule_code === "MISSING_REQUIRED_EXTENSIONS") {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <ul className="mt-1 space-y-2 text-sm text-foreground">
          {sorted.map((item) => {
            const ev = item.evidence ?? {};
            const missing = (ev.missing_extensions as string[] | undefined) ?? [];
            const adId = String(item.ad_external_id ?? ev.ad_id ?? "").trim();
            const cid = String(item.campaign_external_id ?? ev.campaign_id ?? pageCampaignId ?? "").trim();
            const gid = String(item.group_external_id ?? ev.group_id ?? "").trim();
            return (
              <li key={item.id} className="rounded-md border border-border/50 px-2 py-2">
                <p className="font-medium">
                  {yandexLogin && /^\d+$/.test(adId) && /^\d+$/.test(cid) && /^\d+$/.test(gid) ? (
                    <DnaExternalLink href={dnaBannerHref(yandexLogin, cid, gid, adId)}>{adId}</DnaExternalLink>
                  ) : (
                    adId || "—"
                  )}
                </p>
                {missing.length > 0 ? (
                  <p className="mt-1 text-xs text-muted-foreground">Не хватает расширений: {missing.join(", ")}</p>
                ) : null}
              </li>
            );
          })}
        </ul>
      </>
    );
  }

  if (row.rule_code === "GROUP_ALL_ADS_REJECTED") {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <ul className="mt-1 space-y-3 text-sm text-foreground">
          {sorted.map((item) => {
            const ev = item.evidence ?? {};
            const aids = (ev.ad_ids as string[] | undefined) ?? [];
            const gid = String(item.group_external_id ?? ev.group_id ?? "").trim();
            const gname = String(ev.group_name ?? "").trim();
            const cid = String(item.campaign_external_id ?? ev.campaign_id ?? pageCampaignId ?? "").trim();
            return (
              <li key={item.id} className="rounded-md border border-border/50 px-2 py-2">
                <p className="font-medium">{renderLinkedGroupLabel(gid, cid, gname ? ` — ${gname}` : "")}</p>
                {aids.length > 0 ? (
                  <>
                    <p className="mt-1 text-xs text-muted-foreground">Объявления в группе:</p>
                    <ul className="mt-0.5 list-inside list-disc font-mono text-[11px]">
                      {aids.map((raw) => {
                        const aid = String(raw ?? "").trim();
                        return (
                          <li key={`${item.id}-ad-${aid}`}>
                            {yandexLogin && /^\d+$/.test(cid) && /^\d+$/.test(gid) && /^\d+$/.test(aid) ? (
                              <DnaExternalLink href={dnaBannerHref(yandexLogin, cid, gid, aid)}>{aid}</DnaExternalLink>
                            ) : (
                              aid
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </>
                ) : null}
              </li>
            );
          })}
        </ul>
      </>
    );
  }

  if (row.rule_code === "DUPLICATE_SITELINKS") {
    return (
      <>
        <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
        <div className="space-y-3 text-sm text-foreground">
          {sorted.map((item) => {
            const adId = String(item.ad_external_id ?? item.evidence?.ad_id ?? "");
            const clusters =
              (item.evidence?.duplicate_sitelink_clusters as unknown[] | undefined) ??
              item.evidence?.duplicate_sitelinks;
            const idList = item.evidence?.duplicate_sitelinks;
            const lines: string[] = [];
            if (Array.isArray(clusters)) {
              const first = clusters[0];
              if (typeof first === "string") {
                for (const sid of clusters) lines.push(String(sid));
              } else {
                for (const cl of clusters) {
                  if (!Array.isArray(cl)) continue;
                  for (const sl of cl) {
                    if (sl && typeof sl === "object") {
                      const o = sl as Record<string, unknown>;
                      const t = String(o.title ?? "").trim();
                      const u = String(o.url ?? "").trim();
                      const sid = o.sitelink_id != null ? String(o.sitelink_id) : "";
                      if (sid) lines.push(sid + (t ? ` — ${t}` : "") + (u ? ` — ${u}` : ""));
                      else if (t && u) lines.push(`${t} - ${u}`);
                      else if (u) lines.push(u);
                      else if (t) lines.push(t);
                    }
                  }
                }
              }
            }
            const uniq = [...new Set(lines)];
            return (
              <div key={item.id}>
                <p className="font-medium">{adId || "—"}</p>
                {Array.isArray(idList) && idList.length > 0 && typeof idList[0] === "string" ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">ID: {idList.join(", ")}</p>
                ) : null}
                {uniq.length > 0 ? (
                  <ul className="mt-0.5 list-inside list-disc">
                    {uniq.map((line, idx) => (
                      <li key={`${adId}-${idx}-${line.slice(0, 24)}`}>{line}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            );
          })}
        </div>
      </>
    );
  }

  return (
    <>
      <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
      <ul className="mt-1 list-inside list-disc text-sm text-foreground">
        {sorted.map((r) => {
          const ev = (r.evidence ?? {}) as Record<string, unknown>;
          const generic = formatGenericBullet(r);
          const isIssueLocationFallback = generic === r.issue_location;
          if (isIssueLocationFallback) {
            return (
              <li key={r.id}>
                {renderIssueLocationLabel(r.issue_location, yandexLogin, pageCampaignId, r, ev)}
              </li>
            );
          }
          const adId = String(r.ad_external_id ?? ev.ad_id ?? "").trim();
          const cid = String(r.campaign_external_id ?? ev.campaign_id ?? pageCampaignId ?? "").trim();
          const gid = String(r.group_external_id ?? ev.group_id ?? "").trim();
          if (yandexLogin && adId && /^\d+$/.test(adId) && /^\d+$/.test(cid) && /^\d+$/.test(gid)) {
            const title = ev.ad_title != null ? String(ev.ad_title).trim() : "";
            return (
              <li key={r.id}>
                <DnaExternalLink href={dnaBannerHref(yandexLogin, cid, gid, adId)}>{adId}</DnaExternalLink>
                {title ? ` — ${title}` : ""}
              </li>
            );
          }
          return <li key={r.id}>{generic}</li>;
        })}
      </ul>
    </>
  );
}
