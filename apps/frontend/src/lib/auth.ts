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

/** Clears tokens and sends the user to login with a query flag (message only on /login). */
export function redirectToSessionExpiredLogin(): void {
  if (typeof window === "undefined") {
    return;
  }
  clearSession();
  const prefix = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/$/, "");
  window.location.assign(`${prefix}/login?reason=session_expired`);
}
