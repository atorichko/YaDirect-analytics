"use client";

import { SiteHelpLink } from "@/components/site-help-link";

/** Плавающая кнопка справки на всех страницах (в т.ч. без входа в аккаунт). */
export function GlobalHelpAnchor() {
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[100] print:hidden">
      <div className="pointer-events-auto rounded-md border border-border/80 bg-background/95 p-0.5 shadow-md backdrop-blur-sm">
        <SiteHelpLink />
      </div>
    </div>
  );
}
