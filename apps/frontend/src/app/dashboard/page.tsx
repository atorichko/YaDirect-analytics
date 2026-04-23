"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { getApiV1Base } from "@/lib/api-config";

type Me = {
  id: string;
  email: string;
  role: "admin" | "specialist";
  is_active: boolean;
};

export default function DashboardPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [users, setUsers] = useState<Me[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setError("Нет токена — выполните вход.");
      return;
    }
    void (async () => {
      const base = getApiV1Base();
      const res = await fetch(`${base}/users/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setError("Сессия недействительна. Войдите снова.");
        return;
      }
      const data = (await res.json()) as Me;
      setMe(data);
      if (data.role === "admin") {
        const u = await fetch(`${base}/users`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (u.ok) {
          setUsers((await u.json()) as Me[]);
        }
      }
    })();
  }, []);

  function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    const prefix = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/$/, "");
    window.location.href = `${prefix}/login`;
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          {me ? (
            <p className="text-sm text-muted-foreground">
              {me.email} · <span className="font-medium">{me.role}</span>
            </p>
          ) : null}
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" asChild>
            <Link href="/">На главную</Link>
          </Button>
          <Button variant="outline" type="button" onClick={logout}>
            Выйти
          </Button>
        </div>
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {me?.role === "admin" && users ? (
        <section>
          <h2 className="mb-2 text-lg font-medium">Пользователи (только admin)</h2>
          <ul className="list-inside list-disc text-sm text-muted-foreground">
            {users.map((u) => (
              <li key={u.id}>
                {u.email} — {u.role}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </main>
  );
}
