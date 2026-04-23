import Link from "next/link";

import { Button } from "@/components/ui/button";
import { getApiV1Base, getOpenApiDocsUrl } from "@/lib/api-config";

export default function HomePage() {
  const apiV1 = getApiV1Base();

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
        <Button variant="secondary" asChild>
          <Link href={getOpenApiDocsUrl()} target="_blank" rel="noreferrer">
            OpenAPI (backend)
          </Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href={`${apiV1}/health`} target="_blank" rel="noreferrer">
            Health JSON
          </Link>
        </Button>
      </div>
    </main>
  );
}
