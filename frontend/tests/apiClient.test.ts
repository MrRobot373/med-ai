import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, ApiError } from "@/api/client";

describe("apiFetch error handling", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("extracts a plain string `detail` (our own HTTPException bodies)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Invalid email or password" }), {
            status: 401,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );

    await expect(apiFetch("/api/auth/login")).rejects.toMatchObject(
      new ApiError(401, "Invalid email or password"),
    );
  });

  it("flattens FastAPI's validation-error array `detail` instead of stringifying it to [object Object]", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              detail: [{ type: "value_error", loc: ["body", "email"], msg: "Enter a valid email address" }],
            }),
            { status: 422, headers: { "Content-Type": "application/json" } },
          ),
      ),
    );

    const error = await apiFetch("/api/auth/login").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe("Enter a valid email address");
    expect((error as ApiError).message).not.toContain("[object Object]");
  });
});
