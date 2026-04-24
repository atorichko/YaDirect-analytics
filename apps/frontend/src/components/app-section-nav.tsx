"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { apiGet } from "@/lib/api-client";
import { clearSession, getAccessToken } from "@/lib/auth";

type Me = { role: "admin" | "specialist" };

export type AppSection = "rules" | "settings" | "help" | "handoff";

export type AppSectionNavProps = {
  /** Явная подсветка; если не задано — по текущему URL */
  current?: AppSection;
  /** Показать «Главная» и «Выйти» (если есть сессия) */
  showSessionActions?: boolean;
  /** Дополнительные кнопки справа (например, «Запустить аудит») */
  trailing?: ReactNode;
};

function inferSection(pathname: string | null): AppSection | undefined {
  if (!pathname) return undefined;
  const p = pathname.replace(/\/$/, "");
  if (p.endsWith("/rules")) return "rules";
  if (p.endsWith("/settings")) return "settings";
  if (p.endsWith("/help")) return "help";
  if (p.endsWith("/handoff")) return "handoff";
  return undefined;
}

export function AppSectionNav({ current: currentProp, showSessionActions = true, trailing }: AppSectionNavProps) {
  const pathname = usePathname();
  const [token, setToken] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);

  useEffect(() => {
    setToken(getAccessToken());
  }, []);

  const current = currentProp ?? inferSection(pathname);

  useEffect(() => {
    if (!token) {
      setIsAdmin(false);
      return;
    }
    void (async () => {
      try {
        const me = await apiGet<Me>("/users/me", token);
        setIsAdmin(me.role === "admin");
      } catch {
        setIsAdmin(false);
      }
    })();
  }, [token]);

  function logout() {
    clearSession();
    const prefix = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/$/, "");
    window.location.href = `${prefix}/login`;
  }

  function navButton(href: string, label: string, key: AppSection) {
    const active = current === key;
    return (
      <Button key={key} variant={active ? "default" : "secondary"} size="sm" asChild>
        <Link href={href}>{label}</Link>
      </Button>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      <div className="flex flex-wrap items-center gap-2">
        {isAdmin ? (
          <>
            {navButton("/rules", "Правила", "rules")}
            {navButton("/settings", "Настройки", "settings")}
          </>
        ) : null}
        {navButton("/help", "Справка", "help")}
        {isAdmin ? navButton("/handoff", "Handoff", "handoff") : null}
        {showSessionActions ? (
          <>
            <Button variant="secondary" size="sm" asChild>
              <Link href="/dashboard">Главная</Link>
            </Button>
            {token ? (
              <Button variant="outline" size="sm" type="button" onClick={logout}>
                Выйти
              </Button>
            ) : null}
          </>
        ) : null}
      </div>
      {trailing ? <div className="flex flex-wrap items-center gap-2">{trailing}</div> : null}
    </div>
  );
}
