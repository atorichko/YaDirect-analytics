import Link from "next/link";
import type { Metadata } from "next";

import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Главная | YaDirect Analytics",
};

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-6 px-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">YaDirect Analytics</h1>
        <p className="mt-2 text-muted-foreground">
          Внутренний сервис аудита Яндекс Директа. Этап 2: JWT, роли admin/specialist.
        </p>
      </div>
      <div className="flex flex-wrap gap-3">
        <Button asChild>
          <Link href="/login">Войти</Link>
        </Button>
      </div>
    </main>
  );
}
