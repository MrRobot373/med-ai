import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import LoginPage from "@/pages/Login";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function renderLogin() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/overview" element={<div>Overview Page Content</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LoginPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the invalid-credentials error without revealing which field was wrong", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.includes("/api/auth/me")) return jsonResponse({ detail: "Not authenticated" }, 401);
        if (url.includes("/api/auth/login") && init?.method === "POST") {
          return jsonResponse({ detail: "Invalid email or password" }, 401);
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderLogin();

    await user.type(screen.getByLabelText("Email"), "doctor@gms.local");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Sign In" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password.");
  });

  it("logs in successfully and navigates to the redirect target", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.includes("/api/auth/me")) return jsonResponse({ detail: "Not authenticated" }, 401);
        if (url.includes("/api/auth/login") && init?.method === "POST") {
          return jsonResponse({
            id: "u1",
            email: "doctor@gms.local",
            display_name: "Dr. Demo",
            role: "doctor",
            active: true,
            last_login_at: null,
          });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderLogin();

    await user.type(screen.getByLabelText("Email"), "doctor@gms.local");
    await user.type(screen.getByLabelText("Password"), "correct-password");
    await user.click(screen.getByRole("button", { name: "Sign In" }));

    expect(await screen.findByText("Overview Page Content")).toBeInTheDocument();
  });
});
