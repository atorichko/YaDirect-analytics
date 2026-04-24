import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Handoff | Модуль аудита Яндекс Директ",
  description: "Внутренняя справка по YaDirect-analytics для команды и ИИ",
  robots: { index: false, follow: false },
};

export default function HandoffLayout({ children }: { children: ReactNode }) {
  return children;
}
