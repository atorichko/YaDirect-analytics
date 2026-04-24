"use client";

import { useEffect, useMemo, useState } from "react";

import { AppSectionNav } from "@/components/app-section-nav";
import { getAccessToken } from "@/lib/auth";
import { apiGet } from "@/lib/api-client";

type Me = { role: "admin" | "specialist" };

type RuleDefinition = {
  rule_code: string;
  rule_name: string;
  rule_description: string | null;
  fix_recommendation: string | null;
  level: "L1" | "L2" | "L3";
  check_type: "deterministic" | "ai_assisted";
  enabled: boolean;
  config: Record<string, unknown>;
};

type ActiveCatalog = {
  version: string;
  rules: RuleDefinition[];
};

function ruleDescription(rule: RuleDefinition): string {
  if (rule.rule_description && rule.rule_description.trim()) {
    return rule.rule_description.trim();
  }
  const cfg = rule.config ?? {};
  const candidates = [
    cfg.description_ru,
    cfg.description,
    cfg.detection_logic,
    cfg.fail_condition,
    cfg.recommendation_ru,
  ];
  for (const item of candidates) {
    if (typeof item === "string" && item.trim()) {
      return item.trim();
    }
  }
  return "Описание не заполнено в каталоге.";
}

function ruleRecommendation(rule: RuleDefinition): string {
  if (rule.fix_recommendation && rule.fix_recommendation.trim()) {
    return rule.fix_recommendation.trim();
  }
  const cfg = rule.config ?? {};
  const value = cfg.recommendation_ru;
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }
  return "Рекомендация не заполнена в каталоге.";
}

export default function RulesPage() {
  const [error, setError] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<ActiveCatalog | null>(null);
  const token = useMemo(() => getAccessToken(), []);

  useEffect(() => {
    if (!token) {
      setError("Нет токена — выполните вход.");
      return;
    }
    void (async () => {
      try {
        const me = await apiGet<Me>("/users/me", token);
        if (me.role !== "admin") {
          setError("Раздел «Правила» доступен только администратору.");
          return;
        }
        const data = await apiGet<ActiveCatalog>("/rule-catalogs/active", token);
        setCatalog(data);
      } catch {
        setError("Не удалось загрузить активный каталог правил.");
      }
    })();
  }, [token]);

  const aiCodes = useMemo(() => {
    const set = new Set<string>();
    for (const rule of catalog?.rules ?? []) {
      if (rule.check_type === "ai_assisted") {
        set.add(rule.rule_code);
      }
    }
    return set;
  }, [catalog]);

  const rows = useMemo(() => {
    const list = [...(catalog?.rules ?? [])];
    list.sort((a, b) => {
      if (a.level !== b.level) return a.level.localeCompare(b.level);
      return a.rule_name.localeCompare(b.rule_name, "ru");
    });
    return list;
  }, [catalog]);

  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Каталог правил аудита</h1>
          <p className="text-sm text-muted-foreground">
            Активная версия: <span className="font-medium">{catalog?.version ?? "-"}</span>
          </p>
        </div>
        <AppSectionNav current="rules" />
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {catalog ? (
        <section className="overflow-x-auto rounded border">
          <table className="min-w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-3 py-2 text-left">Название проверки</th>
                <th className="px-3 py-2 text-left">Описание</th>
                <th className="px-3 py-2 text-left">Рекомендации по исправлению</th>
                <th className="px-3 py-2 text-left">AI после deterministic</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((rule) => {
                const hasAiAfterDet = rule.check_type === "deterministic" && aiCodes.has(rule.rule_code);
                return (
                  <tr key={`${rule.check_type}:${rule.rule_code}:${rule.level}`} className="border-t align-top">
                    <td className="px-3 py-2">
                      <div className="font-medium">{rule.rule_name}</div>
                      <div className="text-xs text-muted-foreground">
                        {rule.level} · {rule.rule_code} · {rule.check_type}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{ruleDescription(rule)}</td>
                    <td className="px-3 py-2 text-muted-foreground">{ruleRecommendation(rule)}</td>
                    <td className="px-3 py-2">{hasAiAfterDet ? "Да" : "Нет"}</td>
                  </tr>
                );
              })}
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-3 py-6 text-muted-foreground">
                    Нет правил в активном каталоге.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </section>
      ) : null}
    </main>
  );
}
