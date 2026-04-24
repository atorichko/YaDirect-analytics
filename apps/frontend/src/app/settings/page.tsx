"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { SiteHelpLink } from "@/components/site-help-link";
import { Button } from "@/components/ui/button";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api-client";
import { clearSession, getAccessToken } from "@/lib/auth";
import { RECOMMENDED_AI_PROMPT_PREFIX } from "@/lib/recommended-ai-prompt";

type Me = {
  id: string;
  full_name: string;
  email: string;
  role: "admin" | "specialist";
  is_active: boolean;
};

type UserItem = {
  id: string;
  full_name: string;
  email: string;
  role: "admin" | "specialist";
  is_active: boolean;
};

type PromptSettings = {
  prompt: string;
};

type CoverageResponse = {
  catalog_version: string;
  total_rules: number;
  enabled_rules: number;
  implemented_enabled_rules: number;
  missing_enabled_rules: string[];
};

export default function SettingsPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [coverage, setCoverage] = useState<CoverageResponse | null>(null);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"admin" | "specialist">("specialist");
  const [password, setPassword] = useState("");
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [editFullName, setEditFullName] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editPassword, setEditPassword] = useState("");

  const token = useMemo(() => getAccessToken(), []);

  useEffect(() => {
    if (typeof document !== "undefined") {
      document.title = "Настройки | YaDirect Analytics";
    }
  }, []);

  useEffect(() => {
    if (!token) {
      setError("Нет токена — выполните вход.");
      return;
    }
    void (async () => {
      try {
        const meData = await apiGet<Me>("/users/me", token);
        if (meData.role !== "admin") {
          setError("Раздел доступен только администратору.");
          return;
        }
        setMe(meData);
        const [usersData, promptData] = await Promise.all([
          apiGet<UserItem[]>("/users", token),
          apiGet<PromptSettings>("/settings/ai-prompt", token),
        ]);
        setUsers(usersData);
        setPrompt(promptData.prompt);
        try {
          const coverageData = await apiGet<CoverageResponse>("/rule-catalogs/active/coverage", token);
          setCoverage(coverageData);
        } catch {
          setCoverage(null);
        }
      } catch {
        setError("Не удалось загрузить настройки.");
      }
    })();
  }, [token]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("oauth") === "success") {
      const login = params.get("login");
      setInfo(login ? `Кабинет ${login} подключен через OAuth.` : "Кабинет подключен через OAuth.");
    }
  }, []);

  function logout() {
    clearSession();
    const prefix = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/$/, "");
    window.location.href = `${prefix}/login`;
  }

  async function createUser(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setLoading(true);
    setError(null);
    setInfo(null);
    try {
      await apiPost<UserItem>("/users", token, {
        full_name: fullName,
        email,
        role,
        password,
      });
      const usersData = await apiGet<UserItem[]>("/users", token);
      setUsers(usersData);
      setFullName("");
      setEmail("");
      setRole("specialist");
      setPassword("");
      setInfo("Пользователь создан.");
    } catch {
      setError("Не удалось создать пользователя.");
    } finally {
      setLoading(false);
    }
  }

  async function removeUser(userId: string) {
    if (!token) return;
    if (!confirm("Удалить пользователя?")) return;
    setError(null);
    setInfo(null);
    try {
      await apiDelete(`/users/${userId}`, token);
      const usersData = await apiGet<UserItem[]>("/users", token);
      setUsers(usersData);
      setInfo("Пользователь удален.");
    } catch {
      setError("Не удалось удалить пользователя.");
    }
  }

  function startEditUser(user: UserItem) {
    setEditingUserId(user.id);
    setEditFullName(user.full_name);
    setEditEmail(user.email);
    setEditPassword("");
  }

  async function saveUserEdit() {
    if (!token || !editingUserId) return;
    setLoading(true);
    setError(null);
    setInfo(null);
    try {
      await apiPut<UserItem>(`/users/${editingUserId}`, token, {
        full_name: editFullName,
        email: editEmail,
        password: editPassword.trim() ? editPassword : null,
      });
      const usersData = await apiGet<UserItem[]>("/users", token);
      setUsers(usersData);
      setEditingUserId(null);
      setEditFullName("");
      setEditEmail("");
      setEditPassword("");
      setInfo("Пользователь обновлен.");
    } catch {
      setError("Не удалось обновить пользователя.");
    } finally {
      setLoading(false);
    }
  }

  async function savePrompt() {
    if (!token) return;
    setLoading(true);
    setError(null);
    setInfo(null);
    try {
      const updated = await apiPut<PromptSettings>("/settings/ai-prompt", token, { prompt });
      setPrompt(updated.prompt);
      setInfo("Промт сохранен.");
    } catch {
      setError("Не удалось сохранить промт.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Настройки</h1>
          {me ? (
            <p className="text-sm text-muted-foreground">
              {me.full_name} · {me.email}
            </p>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          <SiteHelpLink />
          <Button variant="secondary" asChild>
            <Link href="/handoff">Handoff</Link>
          </Button>
          <Button variant="secondary" asChild>
            <Link href="/dashboard">Dashboard</Link>
          </Button>
          <Button variant="outline" type="button" onClick={logout}>
            Выйти
          </Button>
        </div>
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {info ? <p className="text-sm text-emerald-600">{info}</p> : null}

      <section className="rounded border p-4">
        <h2 className="mb-3 text-lg font-medium">Пользователи</h2>
        <form className="grid gap-2 md:grid-cols-4" onSubmit={createUser}>
          <input
            className="rounded border px-2 py-1 text-sm"
            placeholder="ФИО"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
          />
          <input
            className="rounded border px-2 py-1 text-sm"
            placeholder="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <select className="rounded border px-2 py-1 text-sm" value={role} onChange={(e) => setRole(e.target.value as "admin" | "specialist")}>
            <option value="specialist">specialist</option>
            <option value="admin">admin</option>
          </select>
          <input
            className="rounded border px-2 py-1 text-sm"
            placeholder="Пароль"
            type="text"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Button type="submit" disabled={loading} className="md:col-span-4 md:w-fit">
            Создать
          </Button>
        </form>
        <div className="mt-4 overflow-x-auto rounded border">
          <table className="min-w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-3 py-2 text-left">ФИО</th>
                <th className="px-3 py-2 text-left">Email</th>
                <th className="px-3 py-2 text-left">Роль</th>
                <th className="px-3 py-2 text-left">Действия</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t">
                  <td className="px-3 py-2">{u.full_name}</td>
                  <td className="px-3 py-2">{u.email}</td>
                  <td className="px-3 py-2">{u.role}</td>
                  <td className="px-3 py-2">
                    <div className="flex gap-2">
                      <Button variant="secondary" size="sm" onClick={() => startEditUser(u)}>
                        Редактировать
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => void removeUser(u.id)}
                        disabled={me?.id === u.id}
                      >
                        Удалить
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {users.length === 0 ? (
                <tr>
                  <td className="px-3 py-4 text-muted-foreground" colSpan={4}>
                    Пользователей нет.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      {editingUserId ? (
        <section className="rounded border p-4">
          <h2 className="mb-3 text-lg font-medium">Редактирование пользователя</h2>
          <div className="grid gap-2 md:grid-cols-3">
            <input
              className="rounded border px-2 py-1 text-sm"
              placeholder="ФИО"
              value={editFullName}
              onChange={(e) => setEditFullName(e.target.value)}
            />
            <input
              className="rounded border px-2 py-1 text-sm"
              placeholder="Email"
              type="email"
              value={editEmail}
              onChange={(e) => setEditEmail(e.target.value)}
            />
            <input
              className="rounded border px-2 py-1 text-sm"
              placeholder="Новый пароль (опционально)"
              type="text"
              value={editPassword}
              onChange={(e) => setEditPassword(e.target.value)}
            />
          </div>
          <div className="mt-3 flex gap-2">
            <Button onClick={() => void saveUserEdit()} disabled={loading}>
              Сохранить
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setEditingUserId(null);
                setEditFullName("");
                setEditEmail("");
                setEditPassword("");
              }}
            >
              Отмена
            </Button>
          </div>
        </section>
      ) : null}

      <section className="rounded border p-4">
        <h2 className="mb-3 text-lg font-medium">Промт AI-анализа</h2>
        <p className="mb-2 text-sm text-muted-foreground">
          Префикс задаёт роль модели и формат JSON-ответа; к нему на сервере автоматически добавляются код правила, название и
          данные сущности. Для продакшена используйте рекомендованный шаблон или отредактируйте его под свою политику.
        </p>
        <div className="mb-2">
          <Button variant="secondary" onClick={() => setPrompt(RECOMMENDED_AI_PROMPT_PREFIX)}>
            Подставить рекомендованный промт (продакшен)
          </Button>
        </div>
        <textarea
          className="min-h-56 w-full rounded border px-3 py-2 text-sm"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <div className="mt-3">
          <Button onClick={() => void savePrompt()} disabled={loading}>
            Сохранить промт
          </Button>
        </div>
      </section>

      <section className="rounded border p-4">
        <h2 className="mb-3 text-lg font-medium">Диагностика покрытия правил</h2>
        {coverage ? (
          <div className="space-y-2 text-sm">
            <p>
              Каталог: <span className="font-medium">{coverage.catalog_version}</span>
            </p>
            <p>
              Реализовано активных правил:{" "}
              <span className="font-medium">
                {coverage.implemented_enabled_rules} / {coverage.enabled_rules}
              </span>
            </p>
            {coverage.missing_enabled_rules.length > 0 ? (
              <div>
                <p className="mb-1 text-amber-700">Не реализованы (активные):</p>
                <div className="rounded border bg-amber-50 p-2 font-mono text-xs">
                  {coverage.missing_enabled_rules.join(", ")}
                </div>
              </div>
            ) : (
              <p className="text-emerald-700">Все активные правила каталога покрыты.</p>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Диагностика пока недоступна.</p>
        )}
      </section>
    </main>
  );
}
