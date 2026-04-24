import { getApiV1Base } from "@/lib/api-config";
import { redirectToSessionExpiredLogin } from "@/lib/auth";

type TokenPair = { access_token: string; refresh_token: string };

let refreshInFlight: Promise<string | null> | null = null;

function pendingForever<T>(): Promise<T> {
  return new Promise(() => {});
}

async function refreshAccessToken(): Promise<string | null> {
  if (typeof window === "undefined") {
    return null;
  }
  const rt = localStorage.getItem("refresh_token");
  if (!rt) {
    return null;
  }
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${getApiV1Base()}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: rt }),
        });
        if (!res.ok) {
          return null;
        }
        const data = (await res.json()) as TokenPair;
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("refresh_token", data.refresh_token);
        return data.access_token;
      } catch {
        return null;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

async function parseJsonResponse<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) {
    return undefined as T;
  }
  return JSON.parse(text) as T;
}

async function authorizedJson<T>(
  path: string,
  init: RequestInit,
  token: string,
  allowRefreshRetry: boolean,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${getApiV1Base()}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (res.status === 401 && allowRefreshRetry) {
    const next = await refreshAccessToken();
    if (next) {
      return authorizedJson<T>(path, init, next, false);
    }
    redirectToSessionExpiredLogin();
    return pendingForever();
  }

  if (!res.ok) {
    const details = await res.text();
    const method = (init.method || "GET").toUpperCase();
    throw new Error(`${method} ${path} failed (${res.status}): ${details}`);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return parseJsonResponse<T>(res);
}

export async function apiGet<T>(path: string, token: string): Promise<T> {
  return authorizedJson<T>(path, { method: "GET" }, token, true);
}

export async function apiPost<T>(path: string, token: string, body: unknown): Promise<T> {
  return authorizedJson<T>(
    path,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    token,
    true,
  );
}

export async function apiPut<T>(path: string, token: string, body: unknown): Promise<T> {
  return authorizedJson<T>(
    path,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    token,
    true,
  );
}

export async function apiDelete(path: string, token: string): Promise<void> {
  await authorizedJson<unknown>(path, { method: "DELETE" }, token, true);
}
