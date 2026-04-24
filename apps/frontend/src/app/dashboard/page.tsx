"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppSectionNav } from "@/components/app-section-nav";
import { Button } from "@/components/ui/button";
import type { AdAccount, Me } from "@/features/dashboard/types";
import { getAccessToken } from "@/lib/auth";
import { apiDelete, apiGet, apiPut } from "@/lib/api-client";

export default function DashboardPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [accounts, setAccounts] = useState<AdAccount[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [editingAccountId, setEditingAccountId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");

  useEffect(() => {
    if (typeof document !== "undefined") {
      document.title = "Главная | Модуль аудита Яндекс Директ";
    }
  }, []);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      setError("Нет токена — выполните вход.");
      return;
    }
    void (async () => {
      try {
        const meData = await apiGet<Me>("/users/me", token);
        setMe(meData);
        const accountsData = await apiGet<AdAccount[]>("/ad-accounts", token);
        setAccounts(accountsData);
      } catch {
        setError("Не удалось загрузить данные. Проверьте сеть и попробуйте обновить страницу.");
      }
    })();
  }, []);

  async function removeAccount(accountId: string) {
    const token = getAccessToken();
    if (!token || me?.role !== "admin") return;
    if (!confirm("Удалить подключенный аккаунт?")) return;
    await apiDelete(`/ad-accounts/${accountId}`, token);
    setAccounts((prev) => prev.filter((a) => a.id !== accountId));
    setInfo("Аккаунт удален.");
  }

  async function startOauthConnect() {
    const token = getAccessToken();
    if (!token || me?.role !== "admin") return;
    setError(null);
    setInfo(null);
    try {
      const prefix = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/$/, "");
      const uiRedirect = `${window.location.origin}${prefix}/settings`;
      const projectName = window.prompt("Название проекта для нового кабинета", "")?.trim() ?? "";
      const payload = await apiGet<{ auth_url: string }>(
        `/ad-accounts/oauth/start?ui_redirect=${encodeURIComponent(uiRedirect)}&project_name=${encodeURIComponent(projectName)}`,
        token,
      );
      window.location.href = payload.auth_url;
    } catch {
      setError("Не удалось запустить OAuth-подключение. Проверьте YANDEX_OAUTH_CLIENT_ID.");
    }
  }

  function startEditAccount(account: AdAccount) {
    setEditingAccountId(account.id);
    setEditingName(account.name);
  }

  async function saveAccountName() {
    const token = getAccessToken();
    if (!token || !editingAccountId || me?.role !== "admin") return;
    setError(null);
    setInfo(null);
    try {
      await apiPut<AdAccount>(`/ad-accounts/${editingAccountId}`, token, { name: editingName });
      const accountsData = await apiGet<AdAccount[]>("/ad-accounts", token);
      setAccounts(accountsData);
      setEditingAccountId(null);
      setEditingName("");
      setInfo("Название проекта обновлено.");
    } catch {
      setError("Не удалось обновить название проекта.");
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Модуль аудита Яндекс Директ</h1>
          {me ? (
            <p className="text-sm text-muted-foreground">
              {me.email} · <span className="font-medium">{me.role}</span>
            </p>
          ) : null}
        </div>
        <AppSectionNav />
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {info ? <p className="text-sm text-emerald-600">{info}</p> : null}
      <section className="rounded border p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-lg font-medium">Подключенные аккаунты Яндекс Директ</h2>
          {me?.role === "admin" ? (
            <Button onClick={() => void startOauthConnect()}>Подключить аккаунт Яндекс Директ</Button>
          ) : null}
        </div>
        <div className="overflow-x-auto rounded border">
          <table className="min-w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-3 py-2 text-left">Login</th>
                <th className="px-3 py-2 text-left">Название проекта</th>
                <th className="px-3 py-2 text-left">Дата последней проверки</th>
                <th className="px-3 py-2 text-left">Действия</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((acc) => (
                <tr key={acc.id} className="border-t">
                  <td className="px-3 py-2">
                    <Link className="underline underline-offset-2" href={`/projects/${acc.id}`}>
                      {acc.login}
                    </Link>
                  </td>
                  <td className="px-3 py-2">
                    <Link className="underline underline-offset-2" href={`/projects/${acc.id}`}>
                      {acc.name}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {acc.last_audit_at ? new Date(acc.last_audit_at).toLocaleString("ru-RU") : "еще не запускалась"}
                  </td>
                  <td className="px-3 py-2">
                    {me?.role === "admin" ? (
                      <div className="flex gap-2">
                        <Button variant="secondary" size="sm" onClick={() => startEditAccount(acc)}>
                          Редактировать
                        </Button>
                        <Button variant="destructive" size="sm" onClick={() => void removeAccount(acc.id)}>
                          Удалить
                        </Button>
                      </div>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </td>
                </tr>
              ))}
              {accounts.length === 0 ? (
                <tr>
                  <td className="px-3 py-6 text-muted-foreground" colSpan={4}>
                    Нет подключенных аккаунтов.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
      {editingAccountId ? (
        <section className="rounded border p-4">
          <h2 className="mb-3 text-lg font-medium">Редактирование проекта</h2>
          <div className="flex flex-wrap gap-2">
            <input
              className="min-w-80 rounded border px-3 py-2 text-sm"
              value={editingName}
              onChange={(e) => setEditingName(e.target.value)}
              placeholder="Название проекта"
            />
            <Button onClick={() => void saveAccountName()}>Сохранить</Button>
            <Button
              variant="outline"
              onClick={() => {
                setEditingAccountId(null);
                setEditingName("");
              }}
            >
              Отмена
            </Button>
          </div>
        </section>
      ) : null}
    </main>
  );
}
