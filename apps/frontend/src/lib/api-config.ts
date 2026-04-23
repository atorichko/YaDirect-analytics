/**
 * Browser-accessible API base ending with `/api/v1` (no trailing slash).
 * Production (path deploy): https://atorichko.asur-adigital.ru/YaDirect-analytics/api/v1
 */
export function getApiV1Base(): string {
  const explicit = process.env.NEXT_PUBLIC_API_V1_URL?.trim();
  if (explicit) {
    return explicit.replace(/\/$/, "");
  }
  const origin = (process.env.NEXT_PUBLIC_API_ORIGIN ?? "http://localhost:8000").replace(
    /\/$/,
    "",
  );
  return `${origin}/api/v1`;
}

export function getOpenApiDocsUrl(): string {
  return `${getApiV1Base()}/docs`;
}
