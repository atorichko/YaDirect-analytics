import type { Metadata } from "next";
import type { ReactNode } from "react";

import { GlobalHelpAnchor } from "@/components/global-help-anchor";

import "./globals.css";

export const metadata: Metadata = {
  title: "YaDirect Analytics",
  description: "Internal Yandex Direct campaign audit",
};

export default function RootLayout(props: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body className="min-h-screen antialiased">
        {props.children}
        <GlobalHelpAnchor />
      </body>
    </html>
  );
}
