import type { ReactElement } from "react";

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
    if (row.rule_code === RULE_ACTIVE_CAMPAIGN_WITHOUT_ACTIVE_GROUPS || !MERGE_BY_CAMPAIGN_RULES.has(row.rule_code)) {
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

export function GroupedDetailsSection({ row }: { row: DisplayRow }): ReactElement {
  const rows = row.mergedSourceRows ?? [];
  const sorted = [...rows].sort((a, b) => bulletSortKey(a).localeCompare(bulletSortKey(b)));

  if (row.rule_code === "ACTIVE_AD_REJECTED_OR_RESTRICTED") {
    const byAd = new Map<string, { adId: string; adTitle: string }>();
    for (const item of sorted) {
      const adIdRaw = item.ad_external_id ?? item.evidence?.ad_id;
      if (!adIdRaw) continue;
      const adId = String(adIdRaw);
      const adTitleRaw = item.evidence?.ad_title;
      const adTitle = String(adTitleRaw ?? "").trim() || "Название объявления недоступно";
      if (!byAd.has(adId)) byAd.set(adId, { adId, adTitle });
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
                {item.adId} - {item.adTitle}
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
                {item.groupId} - {item.groupName}
              </li>
            ))}
          </ul>
        </div>
      </>
    );
  }

  return (
    <>
      <p className="mt-2 text-xs font-medium text-muted-foreground">Детали:</p>
      <ul className="mt-1 list-inside list-disc text-sm text-foreground">
        {sorted.map((r) => (
          <li key={r.id}>{formatGenericBullet(r)}</li>
        ))}
      </ul>
    </>
  );
}
