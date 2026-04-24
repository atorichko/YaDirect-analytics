"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { getApiV1Base } from "@/lib/api-config";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sessionExpiredNotice, setSessionExpiredNotice] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (typeof document !== "undefined") {
      document.title = "Вход | YaDirect Analytics";
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const params = new URLSearchParams(window.location.search);
    if (params.get("reason") !== "session_expired") {
      return;
    }
    setSessionExpiredNotice(true);
    params.delete("reason");
    const qs = params.toString();
    const prefix = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/$/, "");
    const path = `${prefix}/login${qs ? `?${qs}` : ""}`;
    window.history.replaceState({}, "", path);
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`${getApiV1Base()}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        setError("Неверный email или пароль");
        return;
      }
      const data = (await res.json()) as {
        access_token: string;
        refresh_token: string;
        token_type: string;
      };
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      router.push("/dashboard");
    } catch {
      setError("Сеть недоступна или сервер не отвечает");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 px-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Вход</h1>
        <p className="mt-1 text-sm text-muted-foreground">YaDirect Analytics</p>
      </div>
      {sessionExpiredNotice ? (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
          Сессия прервалась. Войдите снова.
        </p>
      ) : null}
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          Email
          <input
            className="rounded-md border border-input bg-background px-3 py-2"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Пароль
          <input
            className="rounded-md border border-input bg-background px-3 py-2"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <Button type="submit" disabled={loading}>
          {loading ? "Входим…" : "Войти"}
        </Button>
      </form>
      <Link className="text-sm text-muted-foreground underline-offset-4 hover:underline" href="/">
        На главную
      </Link>
    </main>
  );
}
