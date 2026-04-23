import { getApiV1Base } from "@/lib/api-config";

export async function apiGet<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${getApiV1Base()}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) {
    const details = await res.text();
    throw new Error(`GET ${path} failed (${res.status}): ${details}`);
  }
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, token: string, body: unknown): Promise<T> {
  const res = await fetch(`${getApiV1Base()}${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const details = await res.text();
    throw new Error(`POST ${path} failed (${res.status}): ${details}`);
  }
  return (await res.json()) as T;
}

export async function apiPut<T>(path: string, token: string, body: unknown): Promise<T> {
  const res = await fetch(`${getApiV1Base()}${path}`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const details = await res.text();
    throw new Error(`PUT ${path} failed (${res.status}): ${details}`);
  }
  return (await res.json()) as T;
}

export async function apiDelete(path: string, token: string): Promise<void> {
  const res = await fetch(`${getApiV1Base()}${path}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const details = await res.text();
    throw new Error(`DELETE ${path} failed (${res.status}): ${details}`);
  }
}
