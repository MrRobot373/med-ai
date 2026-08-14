/**
 * Minimal typed fetch wrapper. All API calls should go through this rather than raw
 * `fetch` scattered across components, so credentials/error handling stay consistent
 * once auth (Phase 03) adds cookie-based sessions.
 */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!res.ok) {
    // Never surface a raw stack trace to the UI (spec §92) — the backend already
    // returns a clean error message body for us to display.
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || res.statusText);
  }

  return (await res.json()) as T;
}
