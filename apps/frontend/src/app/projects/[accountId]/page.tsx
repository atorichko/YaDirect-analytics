"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AppSectionNav } from "@/components/app-section-nav";
import { Button } from "@/components/ui/button";
import type { AdAccount, Campaign, JobResponse } from "@/features/dashboard/types";
import { apiGet, apiPost, apiPut } from "@/lib/api-client";
import { getAccessToken } from "@/lib/auth";
import { dnaAccountHref, dnaCampaignHref } from "@/lib/yandex-dna-links";

type Finding = { campaign_external_id: string | null; created_at: string; status: string };

function campaignStatusRu(raw: string | null | undefined): string {
  const s = String(raw ?? "").trim().toUpperCase();
  if (["ON", "ACTIVE", "ENABLED"].includes(s)) return "Активна";
  if (["OFF", "STOPPED", "SUSPENDED"].includes(s)) return "Остановлена";
  if (["ARCHIVED", "ARCHIVE"].includes(s)) return "В архиве";
  if (["ENDED", "CONVERTED"].includes(s)) return "Завершена";
  if (["DRAFT"].includes(s)) return "Черновик";
  if (["MODERATION", "PREMODERATION"].includes(s)) return "На модерации";
  if (["ACCEPTED", "PREACCEPTED"].includes(s)) return "Допущена";
  return raw ? String(raw) : "—";
}

function reportLinkMeta(
  campaignId: string,
  lastAuditMap: Record<string, string>,
  openByCampaign: Record<string, number>,
): { className: string; title: string } {
  const hasAudit = Boolean(lastAuditMap[campaignId]);
  const n = openByCampaign[campaignId] ?? 0;
  if (!hasAudit) {
    return {
      className: "border border-muted-foreground/40 bg-muted/30 text-muted-foreground",
      title: "Отчёт ещё не формировался. Запустите аудит.",
    };
  }
  if (n > 0) {
    return {
      className: "border-2 border-red-500 bg-background text-foreground",
      title: `В отчёте замечаний: ${n}`,
    };
  }
  return {
    className: "border-2 border-emerald-600 bg-background text-foreground",
    title: "В последнем отчёте замечаний нет",
  };
}
type AutostartSettings = { enabled: boolean; every_n_days: number; start_date: string };
type JobStatus = {
  task_id: string;
  state: string;
  ready: boolean;
  successful: boolean | null;
  progress_percent: number | null;
  current_step: string | null;
};
type SortKey = "id" | "name" | "status" | "lastAudit";
type SortDir = "asc" | "desc";
type CampaignAuditTaskMap = Record<string, string>;

export default function ProjectPage() {
  const params = useParams<{ accountId: string }>();
  const accountId = params.accountId;
  const token = useMemo(() => getAccessToken(), []);

  const [account, setAccount] = useState<AdAccount | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [lastAuditMap, setLastAuditMap] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [syncWarning, setSyncWarning] = useState<string | null>(null);
  const [isAutostartOpen, setIsAutostartOpen] = useState(false);
  const [autostart, setAutostart] = useState<AutostartSettings>({
    enabled: false,
    every_n_days: 7,
    start_date: new Date().toISOString().slice(0, 10),
  });
  const [accountAuditTaskId, setAccountAuditTaskId] = useState<string | null>(null);
  const [accountAuditStatus, setAccountAuditStatus] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("status");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [campaignTaskIds, setCampaignTaskIds] = useState<CampaignAuditTaskMap>({});
  const [campaignStatusMap, setCampaignStatusMap] = useState<Record<string, string>>({});
  const [openFindingCountByCampaign, setOpenFindingCountByCampaign] = useState<Record<string, number>>({});
  const [isRefreshingCampaigns, setIsRefreshingCampaigns] = useState(false);
  const [syncStatus, setSyncStatus] = useState<string | null>(null);

  const loadProjectData = useCallback(async (activeToken: string): Promise<{ totalOpen: number; campaignsCount: number }> => {
    const [accountsData, campaignsData, findingsData, autostartData, lastRunMap] = await Promise.all([
      apiGet<AdAccount[]>("/ad-accounts", activeToken),
      apiGet<Campaign[]>(`/ad-accounts/${accountId}/campaigns`, activeToken),
      apiGet<Finding[]>(`/findings?account_id=${accountId}&limit=500`, activeToken),
      apiGet<AutostartSettings>(`/audits/autostart/${accountId}`, activeToken),
      apiGet<Record<string, string>>(`/audits/campaign-last-run/${accountId}`, activeToken),
    ]);
    setAccount(accountsData.find((a) => a.id === accountId) ?? null);
    setCampaigns(campaignsData);
    const openCounts: Record<string, number> = {};
    for (const row of findingsData) {
      if (row.status === "fixed") continue;
      const cid = row.campaign_external_id;
      if (!cid) continue;
      openCounts[cid] = (openCounts[cid] ?? 0) + 1;
    }
    setOpenFindingCountByCampaign(openCounts);
    const totalOpen = Object.values(openCounts).reduce((sum, value) => sum + value, 0);
    const map: Record<string, string> = {};
    for (const row of findingsData) {
      if (!row.campaign_external_id) continue;
      if (!map[row.campaign_external_id] || new Date(row.created_at) > new Date(map[row.campaign_external_id])) {
        map[row.campaign_external_id] = row.created_at;
      }
    }
    for (const [campaignId, lastRun] of Object.entries(lastRunMap)) {
      if (!map[campaignId] || new Date(lastRun) > new Date(map[campaignId])) {
        map[campaignId] = lastRun;
      }
    }
    setLastAuditMap(map);
    setAutostart(autostartData);
    return { totalOpen, campaignsCount: campaignsData.length };
  }, [accountId]);

  useEffect(() => {
    if (typeof document !== "undefined") {
      document.title = account?.name ? `Проект ${account.name} | YaDirect Analytics` : "Проект | YaDirect Analytics";
    }
  }, [account?.name]);

  useEffect(() => {
    if (!token) {
      setError("Нет токена — выполните вход.");
      return;
    }
    void (async () => {
      setError(null);
      setInfo(null);
      setSyncWarning(null);
      try {
        await loadProjectData(token);
        setInfo("Показаны сохраненные данные проекта из базы.");
      } catch (e) {
        if (e instanceof Error && e.message === "UNAUTHORIZED") return;
        setError("Не удалось загрузить проект.");
      }
    })();
  }, [accountId, token, loadProjectData]);

  async function runCampaignAudit(campaignId: string) {
    if (!token) return;
    try {
      const row = await apiPost<JobResponse>("/audits/campaign/run-job", token, {
        account_id: accountId,
        campaign_id: campaignId,
      });
      setInfo(`Аудит кампании ${campaignId} запущен (${row.task_id}).`);
      setCampaignTaskIds((prev) => ({ ...prev, [campaignId]: row.task_id }));
      setCampaignStatusMap((prev) => ({ ...prev, [campaignId]: "Аудит запущен..." }));
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err);
      setError(`Не удалось запустить аудит кампании: ${text}`);
    }
  }

  async function runAllActiveCampaigns() {
    if (!token) return;
    try {
      const result = await apiPost<JobResponse>("/audits/campaigns/run-active-job", token, {
        account_id: accountId,
      });
      setInfo(`Комплексный аудит запущен (${result.task_id}).`);
      setAccountAuditTaskId(result.task_id);
      setAccountAuditStatus("Подготовка аудита: собираем данные по активным кампаниям...");
      const now = new Date().toISOString();
      const activeIds = campaigns
        .filter((c) => ["active", "on", "enabled"].includes(String(c.status || "").toLowerCase()))
        .map((c) => c.id);
      setLastAuditMap((prev) => {
        const next = { ...prev };
        for (const id of activeIds) next[id] = now;
        return next;
      });
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err);
      setAccountAuditStatus("Аудит остановлен из-за ошибки.");
      setError(`Не удалось запустить комплексный аудит: ${text}`);
    }
  }

  async function runSnapshotFallbackAudit() {
    if (!token) return;
    try {
      const result = await apiPost<JobResponse>("/audits/campaigns/run-active-job", token, {
        account_id: accountId,
      });
      setInfo(`Fallback-аудит по snapshot-данным запущен (${result.task_id}).`);
      setAccountAuditTaskId(result.task_id);
      setAccountAuditStatus("Подготовка fallback-аудита: используем локальные данные...");
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err);
      setError(`Не удалось запустить fallback-аудит: ${text}`);
    }
  }

  async function saveAutostart() {
    if (!token) return;
    const updated = await apiPut<AutostartSettings>(`/audits/autostart/${accountId}`, token, autostart);
    setAutostart(updated);
    setInfo("Настройки автозапуска сохранены.");
    setIsAutostartOpen(false);
  }

  async function refreshCampaignsFromApi() {
    if (!token) return;
    try {
      setIsRefreshingCampaigns(true);
      setSyncWarning(null);
      setSyncStatus("Запрос отправлен в Яндекс Директ. Загружаем кампании...");
      const result = await apiPost<{ synced_campaigns: number }>(`/ad-accounts/${accountId}/sync-campaigns`, token, {});
      setInfo(`Кампании обновлены из API Директа: ${result.synced_campaigns}.`);
      await loadProjectData(token);
      setSyncStatus(`Синхронизация завершена: получено кампаний ${result.synced_campaigns}.`);
    } catch (syncErr) {
      const text = syncErr instanceof Error ? syncErr.message : String(syncErr);
      setSyncStatus("Синхронизация ответила ошибкой. Проверяем локальные данные...");
      const beforeCount = campaigns.length;
      if (text.includes("58") || text.toLowerCase().includes("незавершенная регистрация")) {
        setSyncWarning("Не удалось обновить кампании из API Директа. Используем сохраненные snapshot-данные.");
      } else {
        setSyncWarning("Не удалось обновить кампании из API Директа. Загружены локальные snapshot-данные.");
      }
      const loaded = await loadProjectData(token);
      if (loaded.campaignsCount > beforeCount) {
        setInfo(`Данные подтянулись после повторной проверки: ${loaded.campaignsCount} кампаний.`);
        setSyncWarning(null);
        setSyncStatus("Синхронизация в API завершилась с задержкой ответа, но данные в базе обновлены.");
      }
    } finally {
      setIsRefreshingCampaigns(false);
    }
  }

  useEffect(() => {
    if (!token || !accountAuditTaskId) return;
    const timer = window.setInterval(() => {
      void (async () => {
        try {
          const status = await apiGet<JobStatus>(`/audits/jobs/${accountAuditTaskId}`, token);
          if (status.ready) {
            let finalStatus = status.successful ? "Аудит завершен: отчет обновлен (100%)." : "Аудит остановлен из-за ошибки.";
            if (status.successful) {
              const loaded = await loadProjectData(token);
              finalStatus = `Аудит завершен: отчет обновлен (100%). Найдено активных ошибок: ${loaded.totalOpen} по всем кампаниям.`;
            }
            setAccountAuditStatus(finalStatus);
            setAccountAuditTaskId(null);
            return;
          }
          const pct = typeof status.progress_percent === "number" ? status.progress_percent : 0;
          const step = status.current_step ?? "Выполняем аудит...";
          setAccountAuditStatus(`${step} · ${pct}%`);
        } catch {
          // ignore polling transient errors
        }
      })();
    }, 2500);
    return () => window.clearInterval(timer);
  }, [accountAuditTaskId, token, loadProjectData]);

  useEffect(() => {
    if (!token) return;
    const entries = Object.entries(campaignTaskIds);
    if (entries.length === 0) return;
    const timer = window.setInterval(() => {
      void (async () => {
        const done: string[] = [];
        for (const [campaignId, taskId] of entries) {
          try {
            const status = await apiGet<JobStatus>(`/audits/jobs/${taskId}`, token);
            if (!status.ready) {
              const step = status.current_step ?? "Выполняется аудит...";
              const pct = typeof status.progress_percent === "number" ? status.progress_percent : 0;
              setCampaignStatusMap((prev) => ({ ...prev, [campaignId]: `${step} · ${pct}%` }));
              continue;
            }
            if (status.successful) {
              setCampaignStatusMap((prev) => ({ ...prev, [campaignId]: "Аудит завершен" }));
              await loadProjectData(token);
              setInfo(`Аудит кампании ${campaignId} завершен.`);
            } else {
              setCampaignStatusMap((prev) => ({ ...prev, [campaignId]: "Аудит завершился с ошибкой" }));
              setError(`Аудит кампании ${campaignId} завершился с ошибкой.`);
            }
            done.push(campaignId);
          } catch {
            // ignore transient poll errors
          }
        }
        if (done.length > 0) {
          setCampaignTaskIds((prev) => {
            const next = { ...prev };
            for (const key of done) delete next[key];
            return next;
          });
        }
      })();
    }, 2500);
    return () => window.clearInterval(timer);
  }, [campaignTaskIds, token, loadProjectData]);

  function toggleSort(next: SortKey) {
    if (sortKey === next) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(next);
    setSortDir("asc");
  }

  const visibleCampaigns = useMemo(() => {
    const filtered = campaigns.filter((c) => showArchived || String(c.status || "").toUpperCase() !== "ARCHIVED");
    const factor = sortDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      const aLast = lastAuditMap[a.id] ?? "";
      const bLast = lastAuditMap[b.id] ?? "";
      const cmp = (() => {
        if (sortKey === "id") return a.id.localeCompare(b.id, "ru");
        if (sortKey === "name") return String(a.name ?? "").localeCompare(String(b.name ?? ""), "ru");
        if (sortKey === "status") return String(a.status ?? "").localeCompare(String(b.status ?? ""), "ru");
        return aLast.localeCompare(bLast, "ru");
      })();
      return cmp * factor;
    });
  }, [campaigns, lastAuditMap, showArchived, sortKey, sortDir]);

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="mb-1 text-xs text-muted-foreground">
            <Link href="/dashboard" className="hover:underline">
              Аккаунты
            </Link>{" "}
            / <span>Проект</span>
          </p>
          <h1 className="text-2xl font-semibold tracking-tight">Проект: {account?.name ?? "-"}</h1>
          {account ? (
            <p className="text-sm text-muted-foreground">
              аккаунт в Директ:{" "}
              <a
                className="text-blue-700 underline underline-offset-2"
                href={dnaAccountHref(account.login)}
                target="_blank"
                rel="noreferrer"
              >
                {account.login}
              </a>
            </p>
          ) : null}
        </div>
        <AppSectionNav />
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {info ? <p className="text-sm text-emerald-600">{info}</p> : null}
      {accountAuditStatus ? <p className="text-sm text-blue-700">{accountAuditStatus}</p> : null}
      {syncStatus ? <p className="text-sm text-blue-700">{syncStatus}</p> : null}
      {syncWarning ? (
        <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <p>{syncWarning}</p>
          <div className="mt-2">
            <Button variant="secondary" size="sm" onClick={() => void runSnapshotFallbackAudit()}>
              Запустить аудит по локальным snapshot-данным
            </Button>
          </div>
        </div>
      ) : null}

      <section className="rounded border p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-medium">Кампании аккаунта</h2>
          <div className="flex items-center gap-2">
            <span className={accountAuditTaskId ? "audit-play-running inline-flex rounded-md" : "inline-flex"}>
              <Button title="Запустить аудит всех активных кампаний" onClick={() => void runAllActiveCampaigns()}>
                ▶
              </Button>
            </span>
            <Button
              variant="secondary"
              title="Обновить список кампаний из API Директа"
              onClick={() => void refreshCampaignsFromApi()}
              disabled={isRefreshingCampaigns}
            >
              <span className={isRefreshingCampaigns ? "inline-block animate-spin" : "inline-block"}>↻</span>
            </Button>
            <button
              title="Настройки автозапуска"
              className={`rounded border px-3 py-2 text-sm ${autostart.enabled ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-600"}`}
              onClick={() => setIsAutostartOpen((v) => !v)}
            >
              ⚙
            </button>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
              Показывать архивные
            </label>
          </div>
        </div>
        {isAutostartOpen ? (
          <div className="mb-4 rounded border p-3">
            <h3 className="mb-2 text-sm font-medium">Настройки автозапуска</h3>
            <label className="mb-2 flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={autostart.enabled}
                onChange={(e) => setAutostart((prev) => ({ ...prev, enabled: e.target.checked }))}
              />
              Автозапуск отчетов включен
            </label>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span>Запускать отчет каждые</span>
              <input
                className="w-20 rounded border px-2 py-1"
                type="number"
                min={1}
                value={autostart.every_n_days}
                onChange={(e) => setAutostart((prev) => ({ ...prev, every_n_days: Number(e.target.value || 1) }))}
              />
              <span>дней, начиная с даты</span>
              <input
                className="rounded border px-2 py-1"
                type="date"
                value={autostart.start_date}
                onChange={(e) => setAutostart((prev) => ({ ...prev, start_date: e.target.value }))}
              />
              <Button variant="secondary" onClick={() => void saveAutostart()}>
                Сохранить
              </Button>
            </div>
          </div>
        ) : null}
        <div className="overflow-x-auto rounded border">
          <table className="min-w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-3 py-2 text-left">
                  <button className="font-medium" onClick={() => toggleSort("id")}>
                    ID
                  </button>
                </th>
                <th className="px-3 py-2 text-left">
                  <button className="font-medium" onClick={() => toggleSort("name")}>
                    Название
                  </button>
                </th>
                <th className="px-3 py-2 text-left">
                  <button className="font-medium" onClick={() => toggleSort("status")}>
                    Статус
                  </button>
                </th>
                <th className="px-3 py-2 text-left">
                  <button className="font-medium" onClick={() => toggleSort("lastAudit")}>
                    Последний аудит
                  </button>
                </th>
                <th className="px-3 py-2 text-left">Действия</th>
              </tr>
            </thead>
            <tbody>
              {visibleCampaigns.map((c) => (
                <tr key={c.id} className="border-t">
                  <td className="px-3 py-2">
                    {account?.login && /^\d+$/.test(String(c.id)) ? (
                      <a
                        className="text-blue-700 underline underline-offset-2"
                        href={dnaCampaignHref(account.login, String(c.id))}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {c.id}
                      </a>
                    ) : (
                      c.id
                    )}
                  </td>
                  <td className="px-3 py-2">{c.name ?? "-"}</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">{campaignStatusRu(c.status)}</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {lastAuditMap[c.id] ? new Date(lastAuditMap[c.id]).toLocaleString("ru-RU") : "нет"}
                    {campaignStatusMap[c.id] ? <div className="text-[11px] text-blue-700">{campaignStatusMap[c.id]}</div> : null}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-2">
                      <span className={campaignTaskIds[c.id] ? "audit-play-running inline-flex rounded-md" : "inline-flex"}>
                        <Button size="sm" onClick={() => void runCampaignAudit(c.id)}>
                          ▶
                        </Button>
                      </span>
                      {(() => {
                        const meta = reportLinkMeta(c.id, lastAuditMap, openFindingCountByCampaign);
                        return (
                          <Button size="sm" variant="secondary" asChild className={meta.className}>
                            <Link
                              href={`/projects/${accountId}/campaigns/${encodeURIComponent(c.id)}/report`}
                              title={meta.title}
                            >
                              Отчёт
                            </Link>
                          </Button>
                        );
                      })()}
                    </div>
                  </td>
                </tr>
              ))}
              {visibleCampaigns.length === 0 ? (
                <tr>
                  <td className="px-3 py-6 text-muted-foreground" colSpan={5}>
                    Кампаний пока нет.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
