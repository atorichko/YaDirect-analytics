"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { apiGet, apiPost } from "@/lib/api-client";
import { getAccessToken } from "@/lib/auth";

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
  issue_location: string;
  evidence?: {
    group_id?: string;
    group_name?: string;
    keywords?: string[];
    keyword_ids?: string[];
    normalized_keyword?: string;
  } | null;
  impact_ru: string;
  recommendation_ru: string;
  status: string;
  created_at: string;
};

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
  const levels = ["L1", "L2", "L3", "AI"] as const;

  async function loadReport(activeToken: string) {
    const [findings, campaigns] = await Promise.all([
      apiGet<Finding[]>(`/findings?account_id=${accountId}&campaign_id=${encodeURIComponent(campaignId)}&limit=500`, activeToken),
      apiGet<Campaign[]>(`/ad-accounts/${accountId}/campaigns`, activeToken),
    ]);
    setRows(findings);
    setCampaignName(campaigns.find((x) => x.id === campaignId)?.name ?? null);
  }

  useEffect(() => {
    if (!token) return;
    void (async () => {
      try {
        await loadReport(token);
      } catch {
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
        row.evidence?.group_id ?? "",
        row.evidence?.normalized_keyword ?? "",
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
  const fixedHiddenCount = showFixed ? 0 : latestRows.length - visibleRows.length;

  const countByLevel = useMemo(() => {
    const m: Record<string, number> = { L1: 0, L2: 0, L3: 0, AI: 0 };
    for (const row of visibleRows) {
      m[row.level] = (m[row.level] ?? 0) + 1;
    }
    return m;
  }, [visibleRows]);

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

  async function runCampaignAudit() {
    if (!token) return;
    try {
      setError(null);
      const result = await apiPost<JobResponse>("/audits/campaign/run-job", token, {
        account_id: accountId,
        campaign_id: campaignId,
      });
      setInfo(`Аудит кампании запущен (${result.task_id}).`);
      setAuditTaskId(result.task_id);
      setAuditStatus("Аудит запущен...");
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err);
      setError(`Не удалось запустить аудит: ${text}`);
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
          <h1 className="text-2xl font-semibold tracking-tight">Отчет кампании: {campaignName ?? campaignId}</h1>
          <p className="text-sm text-muted-foreground">ID кампании: {campaignId}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={() => void runCampaignAudit()}>▶ Запустить аудит</Button>
          <Button variant="secondary" asChild>
            <Link href={`/projects/${accountId}`}>К кампании</Link>
          </Button>
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
          </div>
        ))}
      </section>

      <div className="overflow-x-auto rounded border">
        <table className="min-w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-3 py-2 text-left">Правило</th>
              <th className="px-3 py-2 text-left">Критичность</th>
              <th className="px-3 py-2 text-left">Уровень</th>
              <th className="px-3 py-2 text-left">Статус</th>
              <th className="px-3 py-2 text-left">Детали</th>
              <th className="px-3 py-2 text-left">Дата</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => (
              <tr key={row.id} className="border-t">
                <td className="px-3 py-2">{row.rule_name}</td>
                <td className="px-3 py-2">{severityRu(row.severity)}</td>
                <td className="px-3 py-2">{row.level}</td>
                <td className="px-3 py-2">{statusRu(row.status)}</td>
                <td className="px-3 py-2">
                  {row.rule_code === "DUPLICATE_KEYWORDS_IN_GROUP" ? (
                    <div className="space-y-1">
                      <p>
                        Группа: <span className="font-medium">{row.evidence?.group_name ?? "-"}</span> (ID:{" "}
                        {row.evidence?.group_id ?? row.group_external_id ?? "-"})
                      </p>
                      <p className="text-muted-foreground">Дублирующиеся фразы:</p>
                      <div className="rounded border bg-muted/40 p-2">
                        {(row.evidence?.keywords ?? []).map((kw, idx) => (
                          <div key={`${row.id}-${idx}`}>- {kw}</div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-1">
                      <p>{row.impact_ru}</p>
                      <p className="text-muted-foreground">{row.recommendation_ru}</p>
                    </div>
                  )}
                </td>
                <td className="px-3 py-2 text-muted-foreground">{new Date(row.created_at).toLocaleString("ru-RU")}</td>
              </tr>
            ))}
            {visibleRows.length === 0 ? (
              <tr>
                <td className="px-3 py-6 text-muted-foreground" colSpan={6}>
                  По кампании пока нет находок.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </main>
  );
}
