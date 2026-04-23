export function getAccessToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return localStorage.getItem("access_token");
}

export function clearSession(): void {
  if (typeof window === "undefined") {
    return;
  }
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}
