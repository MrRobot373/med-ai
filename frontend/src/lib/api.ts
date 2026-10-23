export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) {
    super(message);
  }
}

type Opts = Omit<RequestInit, "body"> & { body?: unknown; query?: Record<string, string | number | boolean | null | undefined> };

function buildUrl(path: string, query?: Opts["query"]) {
  if (!query) return path;
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  const s = qs.toString();
  return s ? `${path}?${s}` : path;
}

export async function api<T = unknown>(path: string, opts: Opts = {}): Promise<T> {
  const { body, query, headers, ...rest } = opts;
  const isForm = body instanceof FormData;
  let res: Response;
  try {
    res = await fetch(buildUrl(path, query), {
      credentials: "include",
      ...rest,
      headers: { ...(body !== undefined && !isForm ? { "Content-Type": "application/json" } : {}), ...headers },
      body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check that the backend is running.");
  }
  if (res.status === 401 && !path.startsWith("/api/auth/login")) {
    window.dispatchEvent(new CustomEvent("gms:unauthorized"));
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    let code: string | undefined;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = data.detail.map((d: any) => d.msg).join("; ");
      code = data.code;
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, message, code);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") ?? "";
  return (ct.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

/** POST that returns a Server-Sent Events stream; calls onEvent per event. */
export async function streamSSE(path: string, body: unknown, onEvent: (event: string, data: any) => void, signal?: AbortSignal) {
  const res = await fetch(path, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    let message = `Request failed (${res.status})`;
    try {
      message = (await res.json()).detail ?? message;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, message);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
      }
      if (data.length) {
        try {
          onEvent(event, JSON.parse(data.join("\n")));
        } catch {
          onEvent(event, data.join("\n"));
        }
      }
    }
  }
}
