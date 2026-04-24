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

  if (row.rule_code === "DUPLICATE_KEYWORDS_IN_GROUP") {
    type Conflict = { keyword_id: string; phrase: string; minus_tokens: string[] };
    const byGroup = new Map<
      string,
      { groupId: string; groupName: string; duplicates: string[]; conflicts: Conflict[] }
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
                  {g.groupId} - {g.groupName}
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
            let prefix = "";
            if (kind === "cross_campaign") prefix = `${lc} ↔ ${rc}: `;
            else if (kind === "cross_group") prefix = `${lg} ↔ ${rg}: `;
            else if (lg) prefix = `группа ${lg}: `;
            return (
              <li key={r.id}>
                {prefix}«{lk}» и «{rk}»
              </li>
            );
          })}
        </ul>
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
                  Объявления: {aids.join(", ")}
                  {sig?.title != null || sig?.url != null ? (
                    <span className="block text-xs">
                      {String(sig.title ?? "")} · {String(sig.url ?? "")}
                    </span>
                  ) : null}
                </p>
                {sums.length > 0 ? (
                  <ul className="mt-1 list-inside list-disc">
                    {sums.map((s, idx) => (
                      <li key={`${item.id}-${s.ad_id ?? idx}`}>
                        {String(s.ad_id ?? "")}: {String(s.caption_ru ?? "")}
                      </li>
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
        {sorted.map((r) => (
          <li key={r.id}>{formatGenericBullet(r)}</li>
        ))}
      </ul>
    </>
  );
}
