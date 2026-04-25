"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { apiGet, apiPost } from "@/lib/api-client";

type CoverageResponse = {
  catalog_version: string;
  catalog_updated_at?: string;
  ai_appendix_rule_codes?: string[];
  total_rules: number;
  enabled_rules: number;
  implemented_enabled_rules: number;
  missing_enabled_rules: string[];
};

type PublishBundledResponse = {
  catalog_version_used: string;
  catalog_id: string;
  activated: boolean;
  bundle_path: string;
};

function formatCatalogUpdated(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export type PublishBundledCatalogBlockProps = {
  token: string | null;
  disabled?: boolean;
  /** После успешной публикации (например, перезагрузить таблицу правил). */
  onPublished?: () => void | Promise<void>;
};

export function PublishBundledCatalogBlock({ token, disabled, onPublished }: PublishBundledCatalogBlockProps) {
  const [busy, setBusy] = useState(false);
  const [statusLine, setStatusLine] = useState<string | null>(null);
  const [statusTone, setStatusTone] = useState<"neutral" | "success" | "error">("neutral");
  const [lastUpdatedIso, setLastUpdatedIso] = useState<string | null>(null);

  const refreshMeta = useCallback(async () => {
    if (!token) return;
    try {
      const cov = await apiGet<CoverageResponse>("/rule-catalogs/active/coverage", token);
      setLastUpdatedIso(cov.catalog_updated_at ?? null);
    } catch {
      setLastUpdatedIso(null);
    }
  }, [token]);

  useEffect(() => {
    void refreshMeta();
  }, [refreshMeta]);

  async function publishBundledCatalog() {
    if (!token) return;
    if (
      !confirm(
        "Загрузить встроенный rule-catalog.json с сервера в базу и сделать его активным? Текущий активный каталог будет снят с публикации и заменён новым.",
      )
    ) {
      return;
    }
    setBusy(true);
    setStatusTone("neutral");
    setStatusLine("Публикация встроенного каталога, загрузка в БД и активация…");
    try {
      const res = await apiPost<PublishBundledResponse>("/rule-catalogs/publish-bundled", token, {
        activate: true,
      });
      setStatusTone("success");
      setStatusLine(
        `Готово: версия ${res.catalog_version_used}, активирован: ${res.activated ? "да" : "нет"}. Файл на сервере: ${res.bundle_path}.`,
      );
      await refreshMeta();
      await onPublished?.();
    } catch (e) {
      setStatusTone("error");
      setStatusLine(e instanceof Error ? e.message : "Не удалось опубликовать каталог.");
    } finally {
      setBusy(false);
    }
  }

  const statusClass =
    statusTone === "error"
      ? "text-destructive"
      : statusTone === "success"
        ? "text-emerald-700"
        : "text-muted-foreground";

  return (
    <div className="space-y-2">
      <Button
        type="button"
        variant="secondary"
        disabled={busy || disabled || !token}
        onClick={() => void publishBundledCatalog()}
      >
        {busy ? "Публикация…" : "Опубликовать встроенный каталог и активировать"}
      </Button>
      {statusLine ? <p className={`text-sm ${statusClass}`}>{statusLine}</p> : null}
      <p className="text-xs text-muted-foreground">
        Дата последнего обновления каталога в БД:{" "}
        <span className="font-medium text-foreground">{formatCatalogUpdated(lastUpdatedIso)}</span>
      </p>
    </div>
  );
}
