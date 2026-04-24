import Link from "next/link";
import type { Metadata } from "next";

import { AppSectionNav } from "@/components/app-section-nav";
import catalog from "@/data/rule-catalog.json";

export const metadata: Metadata = {
  title: "Справка по проверкам | YaDirect Analytics",
};

type CatalogRule = {
  rule_code: string;
  name_ru: string;
  severity: string;
  level: string;
  entity_type?: string;
  detection_logic?: string;
  recommendation_ru?: string;
};

type CatalogFile = {
  severity_enum: Record<string, string>;
  rules: CatalogRule[];
};

const data = catalog as CatalogFile;

const ENTITY_RU: Record<string, string> = {
  campaign: "кампания",
  group: "группа объявлений",
  ad: "объявление",
  keyword: "ключевая фраза",
  ad_extension: "расширение объявления",
};

const IMPACT_RU: Record<string, string> = {
  warning:
    "Обычно не останавливает показы сразу, но ухудшает управляемость, чистоту семантики или качество данных для оптимизации.",
  high: "Может приводить к заметной потере трафика и бюджета, внутренней конкуренции или неверным решениям стратегии.",
  critical:
    "Может приводить к фактической остановке показов, отклонениям модерации, конфликтам таргетинга или серьёзным потерям эффективности.",
};

const LEVEL_LEGEND: { id: string; title: string; body: string }[] = [
  {
    id: "L1",
    title: "L1 — базовая целостность",
    body: "Структура аккаунта, семантика, модерация, дубли, минус-слова, расширения. Без внешних HTTP-проверок ссылок.",
  },
  {
    id: "L2",
    title: "L2 — стратегия и ограничения",
    body: "Стратегии показа, бюджеты, цели и конверсии, обучение, ограничения, согласованность с Метрикой и целями.",
  },
  {
    id: "L3",
    title: "L3 — техническая валидность",
    body: "Финальные URL, редиректы, SSL, обязательная разметка (UTM), технические риски посадочных страниц.",
  },
];

function entityRu(raw: string | undefined): string {
  if (!raw) return "сущность";
  return ENTITY_RU[raw] ?? raw;
}

function levelOrder(lvl: string): number {
  if (lvl === "L1") return 1;
  if (lvl === "L2") return 2;
  if (lvl === "L3") return 3;
  return 9;
}

export default function HelpPage() {
  const rules = [...data.rules].sort((a, b) => {
    const d = levelOrder(a.level) - levelOrder(b.level);
    if (d !== 0) return d;
    return a.name_ru.localeCompare(b.name_ru, "ru");
  });

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-8 px-6 py-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Справка по проверкам</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Ниже перечислены детерминированные правила из каталога (как в продукте). Дополнительно выполняются AI-assisted
            проверки по тем же уровням: они настраиваются в активном каталоге правил и используют отдельный промпт в разделе
            «Настройки».
          </p>
        </div>
        <AppSectionNav current="help" />
      </div>

      <section className="rounded-lg border bg-card p-5 shadow-sm">
        <h2 className="text-lg font-medium">Уровни L1, L2, L3</h2>
        <ul className="mt-3 space-y-3 text-sm">
          {LEVEL_LEGEND.map((item) => (
            <li key={item.id}>
              <p className="font-medium text-foreground">{item.title}</p>
              <p className="mt-1 text-muted-foreground">{item.body}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="overflow-x-auto rounded-lg border shadow-sm">
        <table className="min-w-full text-sm">
          <thead className="bg-muted/80">
            <tr>
              <th className="px-3 py-2 text-left font-medium">Проверка</th>
              <th className="px-3 py-2 text-left font-medium">Уровень</th>
              <th className="px-3 py-2 text-left font-medium">Что проверяет</th>
              <th className="px-3 py-2 text-left font-medium">На что влияет</th>
              <th className="px-3 py-2 text-left font-medium">Критичность</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((rule) => {
              const sevLabel = data.severity_enum[rule.severity] ?? rule.severity;
              const impact = IMPACT_RU[rule.severity] ?? IMPACT_RU.warning;
              const checks = [
                `Объект: ${entityRu(rule.entity_type)}.`,
                rule.detection_logic ? `Условие (внутренняя логика): ${rule.detection_logic}.` : null,
              ]
                .filter(Boolean)
                .join(" ");
              return (
                <tr key={rule.rule_code} className="border-t align-top">
                  <td className="px-3 py-2 font-medium">{rule.name_ru}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{rule.level}</td>
                  <td className="px-3 py-2 text-muted-foreground">{checks}</td>
                  <td className="px-3 py-2 text-muted-foreground">{impact}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{sevLabel}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </main>
  );
}
