import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { UserMenu } from "@/components/UserMenu";

const DEMO_USER = {
  id: "u1",
  email: "doctor@gms.local",
  display_name: "Dr. Demo",
  role: "doctor",
  active: true,
  last_login_at: null,
};

function renderUserMenu() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // Seed the "me" cache directly — UserMenu is always rendered inside an already
  // RequireAuth-gated tree in the real app, so it doesn't re-fetch /me itself here.
  queryClient.setQueryData(["auth", "me"], DEMO_USER);

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/overview"]}>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route path="/overview" element={<UserMenu />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("UserMenu", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the current user's name and role once opened", async () => {
    const user = userEvent.setup();
    renderUserMenu();

    await user.click(screen.getByRole("button", { name: /Dr\. Demo/i }));

    expect(screen.getByText("doctor@gms.local")).toBeInTheDocument();
  });

  it("logs out and navigates to /login on click", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("/api/auth/logout")) return new Response(null, { status: 204 });
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderUserMenu();
    await user.click(screen.getByRole("button", { name: /Dr\. Demo/i }));
    await user.click(screen.getByRole("menuitem", { name: /Logout/i }));

    await waitFor(() => expect(screen.getByText("Login Page")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/auth/logout"),
      expect.objectContaining({ method: "POST" }),
    );
  });
});
