/**
 * Minimal typed fetch wrapper. All API calls should go through this rather than raw
 * `fetch` scattered across components, so credentials/error handling stay consistent.
 * `credentials: "include"` is required for the auth cookie to be sent/received
 * cross-port in dev (localhost:5173 -> localhost:8000 is same-site, different origin).
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
    // Never surface a raw stack trace to the UI (spec §92). FastAPI error bodies come
    // in two shapes: our own `HTTPException(detail="...")` (a string) and its
    // automatic request-validation 422s (`detail: [{ msg, loc, ... }, ...]`) — both
    // must resolve to a plain, readable string, never an object handed to `Error()`
    // (which silently stringifies to the useless "[object Object]").
    const raw = await res.text().catch(() => "");
    let message = raw || res.statusText;
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === "string") {
        message = parsed.detail;
      } else if (Array.isArray(parsed.detail)) {
        const joined = parsed.detail
          .map((e) => (e && typeof e === "object" && "msg" in e ? String((e as { msg: unknown }).msg) : null))
          .filter((m): m is string => Boolean(m))
          .join("; ");
        if (joined) message = joined;
      }
    } catch {
      // body wasn't JSON — keep the raw/status-text fallback above
    }
    throw new ApiError(res.status, message);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}
