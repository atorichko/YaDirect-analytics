import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function HomePage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-6 px-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Yandex Direct Audit</h1>
        <p className="mt-2 text-muted-foreground">
          MVP bootstrap: Next.js + FastAPI monorepo. Этап 1 — каркас без авторизации и БД.
        </p>
      </div>
      <div className="flex flex-wrap gap-3">
        <Button asChild>
          <Link href={`${apiUrl}/api/v1/docs`} target="_blank" rel="noreferrer">
            OpenAPI (backend)
          </Link>
        </Button>
        <Button variant="secondary" asChild>
          <Link href={`${apiUrl}/api/v1/health`} target="_blank" rel="noreferrer">
            Health JSON
          </Link>
        </Button>
      </div>
    </main>
  );
}
