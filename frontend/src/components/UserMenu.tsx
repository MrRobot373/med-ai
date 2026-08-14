import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, LogOut } from "lucide-react";
import { useLogout, useMe } from "@/api/auth";

/**
 * Spec §19 user menu. Only "Logout" is real — Profile/Preferences/System Information
 * have no destination yet (no such pages exist), so rather than list them as dead
 * clicks this menu only shows what's actually built, per the NotYetBuilt philosophy
 * applied to menus instead of routes.
 */
export function UserMenu() {
  const { data: user } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (!user) return null;

  const initials =
    user.display_name
      .split(" ")
      .map((part) => part[0])
      .filter(Boolean)
      .slice(0, 2)
      .join("")
      .toUpperCase() || "?";

  function handleLogout() {
    logout.mutate(undefined, {
      onSuccess: () => navigate("/login", { replace: true }),
    });
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-md px-1.5 py-1 text-sm transition-colors hover:bg-light-blue"
      >
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-blue text-xs font-semibold text-white">
          {initials}
        </span>
        <span className="hidden text-left leading-tight md:block">
          <span className="block text-xs font-medium text-navy">{user.display_name}</span>
          <span className="block text-[11px] capitalize text-muted-text">{user.role}</span>
        </span>
        <ChevronDown className="h-3.5 w-3.5 text-muted-text" />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-20 mt-2 w-56 rounded-lg border border-border bg-surface py-1 shadow-md"
        >
          <div className="border-b border-border px-3 py-2">
            <div className="text-sm font-medium text-navy">{user.display_name}</div>
            <div className="truncate text-xs text-muted-text">{user.email}</div>
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={handleLogout}
            disabled={logout.isPending}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-danger transition-colors hover:bg-danger/5 disabled:opacity-60"
          >
            <LogOut className="h-4 w-4" />
            {logout.isPending ? "Signing out…" : "Logout"}
          </button>
        </div>
      )}
    </div>
  );
}
