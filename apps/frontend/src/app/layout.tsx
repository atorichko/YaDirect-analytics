import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "Yandex Direct Audit",
  description: "Internal QA for Yandex Direct campaign setup",
};

export default function RootLayout(props: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body className="min-h-screen antialiased">{props.children}</body>
    </html>
  );
}
