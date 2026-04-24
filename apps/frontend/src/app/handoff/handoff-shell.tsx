"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import { AppSectionNav } from "@/components/app-section-nav";
import { apiGet } from "@/lib/api-client";
import { getAccessToken } from "@/lib/auth";

type Me = { role: "admin" | "specialist" };

export default function HandoffShell({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);

  useEffect(() => {
    const t = getAccessToken();
    setToken(t);
    if (!t) {
      setIsAdmin(false);
      return;
    }
    void (async () => {
      try {
        const me = await apiGet<Me>("/users/me", t);
        setIsAdmin(me.role === "admin");
      } catch {
        setIsAdmin(false);
      }
    })();
  }, []);

  return (
    <main className="mx-auto max-w-3xl space-y-10 px-4 py-10 text-sm leading-relaxed md:px-6">
      <header className="space-y-3 border-b pb-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Handoff</h1>
            <p className="text-sm text-muted-foreground">Внутренний контекст проекта и правила эксплуатации.</p>
          </div>
          <AppSectionNav current="handoff" />
        </div>
        <p className="text-muted-foreground">
          Кратко по сути (ориентир — «легенда» уровней L1/L2/L3 в{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">temp/легенда.txt</code>
          ), архитектура, окружение, Docker/nginx, выкладка и единый каталог правил.
        </p>
        <p className="text-muted-foreground">
          Пользовательская справка по проверкам:{" "}
          <Link href="/help" className="text-primary underline-offset-4 hover:underline">
            /help
          </Link>
          .
        </p>
      </header>

      {!token ? (
        <p className="text-sm text-destructive">Войдите в систему, чтобы открыть этот раздел.</p>
      ) : isAdmin === false ? (
        <p className="text-sm text-destructive">Раздел Handoff доступен только администратору.</p>
      ) : isAdmin === true ? (
        children
      ) : (
        <p className="text-sm text-muted-foreground">Проверка доступа…</p>
      )}
    </main>
  );
}
