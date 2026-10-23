import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useQueryClient } from "@tanstack/react-query";
import { Inbox, Menu, MessageSquarePlus, Moon, Plus, Search, Sun, Upload, UserPlus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { useBranding, useInbox, useMe } from "@/api/hooks";
import { useAppearance } from "@/app/appearance";
import { Button, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, Kbd, SheetContent, Spinner, Tooltip } from "@/components/ui";
import { cn } from "@/lib/utils";
import { BrandMark } from "./BrandMark";
import { CommandPaletteProvider, usePalette } from "./CommandPalette";
import { NAV, PRIMARY_NAV, RAIL_NAV } from "./nav";
import { StatusIndicator } from "./StatusIndicator";
import { UserMenu } from "./UserMenu";

/** Keyboard "go to" shortcuts: G then H/I/P/A/L/S. */
function useGoShortcuts() {
  const navigate = useNavigate();
  const pending = useRef(false);
  useEffect(() => {
    const map: Record<string, string> = { h: "/", i: "/inbox", p: "/patients", a: "/assistant", l: "/library", s: "/settings" };
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName) || e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (pending.current && map[k]) {
        navigate(map[k]);
        pending.current = false;
        return;
      }
      pending.current = k === "g";
      if (pending.current) setTimeout(() => (pending.current = false), 1200);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate]);
}

const iconBtn = "glass relative flex size-10 items-center justify-center rounded-xl border border-white/70 text-muted-foreground shadow-card transition-colors hover:text-foreground dark:border-white/[0.06] [&_svg]:size-[18px]";

function TopBar() {
  const palette = usePalette();
  const { resolvedTheme, update } = useAppearance();
  const { data: me } = useMe();
  const { data: inbox } = useInbox();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const urgent = inbox?.filter((i) => i.priority !== "low").length ?? 0;
  const isMac = typeof navigator !== "undefined" && /Mac/i.test(navigator.platform);

  return (
    <header className="no-print sticky top-0 z-30 bg-background/70 px-3 py-3 backdrop-blur-md md:px-6 md:py-4">
      <div className="flex items-center gap-3">
        <DialogPrimitive.Root open={mobileOpen} onOpenChange={setMobileOpen}>
          <DialogPrimitive.Trigger asChild>
            <button className={cn(iconBtn, "md:hidden")} aria-label="Open navigation"><Menu /></button>
          </DialogPrimitive.Trigger>
          <SheetContent title={<BrandMark />} width="max-w-[290px] left-0 right-auto border-l-0 border-r">
            <nav className="space-y-4 p-3">
              {NAV.map((g) => (
                <div key={g.group}>
                  <div className="text-label mb-1 px-2">{g.group}</div>
                  {g.items.filter((i) => !i.roles || (me && i.roles.includes(me.role))).map((i) => (
                    <NavLink key={i.to} to={i.to} end={i.to === "/"} onClick={() => setMobileOpen(false)} className={({ isActive }) => cn("flex items-center gap-2.5 rounded-full px-3 py-2 text-sm font-medium", isActive ? "bg-strong text-strong-foreground" : "hover:bg-muted")}>
                      <i.icon className="size-4" /> {i.label}
                    </NavLink>
                  ))}
                </div>
              ))}
            </nav>
          </SheetContent>
        </DialogPrimitive.Root>

        <BrandMark className="shrink-0" showText />

        <nav className="glass mx-auto hidden items-center gap-1 rounded-full border border-white/70 p-1 shadow-card dark:border-white/[0.06] md:flex">
          {PRIMARY_NAV.map((item) => (
            <NavLink
              key={item.to} to={item.to} end={item.to === "/"}
              className={({ isActive }) => cn(
                "relative flex items-center gap-2 rounded-full px-4 py-2 text-[0.84rem] font-medium transition-all",
                isActive ? "bg-strong text-strong-foreground shadow-card" : "text-muted-foreground hover:bg-muted/80 hover:text-foreground",
              )}
            >
              <item.icon className="size-4" strokeWidth={1.9} />
              {item.label}
              {item.badge === "inbox" && urgent > 0 && <span className="ml-0.5 rounded-full bg-danger px-1.5 text-[0.65rem] font-semibold leading-[1.1rem] text-white num">{urgent > 99 ? "99+" : urgent}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2 md:ml-0">
          <Tooltip content={<span className="flex items-center gap-1">Search <Kbd className="bg-transparent text-background/80">{isMac ? "⌘K" : "Ctrl K"}</Kbd></span>}>
            <button className={iconBtn} onClick={palette.open} aria-label="Search"><Search /></button>
          </Tooltip>
          <Tooltip content={resolvedTheme === "dark" ? "Light theme" : "Dark theme"}>
            <button className={cn(iconBtn, "hidden sm:flex")} onClick={() => update({ theme: resolvedTheme === "dark" ? "light" : "dark" })} aria-label="Toggle theme">
              {resolvedTheme === "dark" ? <Sun /> : <Moon />}
            </button>
          </Tooltip>
          <Tooltip content="Inbox">
            <Link to="/inbox" className={cn(iconBtn, "gap-1.5 px-3 w-auto")} aria-label="Inbox">
              <Inbox /><span className="text-[0.8rem] font-semibold text-foreground num">{urgent}</span>
            </Link>
          </Tooltip>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="strong" className="hidden h-10 rounded-xl px-3.5 sm:inline-flex"><Plus /> New</Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56">
              {me?.role !== "viewer" && <DropdownMenuItem onSelect={() => navigate("/patients?new=1")}><UserPlus /> Patient</DropdownMenuItem>}
              <DropdownMenuItem onSelect={() => navigate("/assistant?new=1")}><MessageSquarePlus /> Conversation</DropdownMenuItem>
              {me?.role === "admin" && <DropdownMenuItem onSelect={() => navigate("/library?upload=1")}><Upload /> Library document</DropdownMenuItem>}
            </DropdownMenuContent>
          </DropdownMenu>
          <UserMenu />
        </div>
      </div>
      <nav className="mt-3 flex gap-1 overflow-x-auto md:hidden">
        {PRIMARY_NAV.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === "/"} className={({ isActive }) => cn("flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium", isActive ? "bg-strong text-strong-foreground" : "glass border text-muted-foreground")}>
            <item.icon className="size-3.5" /> {item.label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}

function Rail() {
  const { data: me } = useMe();
  return (
    <aside className="no-print sticky top-[88px] hidden h-fit shrink-0 md:block">
      <div className="glass flex flex-col items-center gap-1.5 rounded-full border border-white/70 p-1.5 shadow-card dark:border-white/[0.06]">
        {RAIL_NAV.filter((i) => !i.roles || (me && i.roles.includes(me.role))).map((item) => (
          <Tooltip key={item.to} content={item.label} side="right">
            {/* span wrapper: Radix Slot would stringify NavLink's function className */}
            <span className="block">
            <NavLink
              to={item.to}
              className={({ isActive }) => cn(
                "flex size-10 items-center justify-center rounded-full transition-all",
                isActive ? "bg-strong text-strong-foreground shadow-card" : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
              aria-label={item.label}
            >
              <item.icon className="size-[18px]" strokeWidth={1.85} />
            </NavLink>
            </span>
          </Tooltip>
        ))}
        <div className="my-1 h-px w-6 bg-border" />
        <div className="w-10"><StatusIndicator collapsed /></div>
      </div>
    </aside>
  );
}

export function AppShell() {
  const { data: me, isLoading, isError } = useMe();
  const { data: branding } = useBranding();
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  useGoShortcuts();

  useEffect(() => {
    const onUnauthorized = () => {
      qc.removeQueries({ queryKey: ["me"] });
      navigate(`/login?next=${encodeURIComponent(location.pathname + location.search)}`, { replace: true });
    };
    window.addEventListener("gms:unauthorized", onUnauthorized);
    return () => window.removeEventListener("gms:unauthorized", onUnauthorized);
  }, [navigate, location, qc]);

  useEffect(() => {
    if (isError) navigate(`/login?next=${encodeURIComponent(location.pathname + location.search)}`, { replace: true });
  }, [isError, navigate, location]);

  if (isLoading || !me) {
    return <div className="flex h-screen items-center justify-center"><Spinner className="size-5" /></div>;
  }

  const fullBleed = location.pathname.startsWith("/assistant");
  return (
    <CommandPaletteProvider>
      <div className="min-h-screen">
        <TopBar />
        <div className="mx-auto flex w-full max-w-[1680px] gap-4 px-3 pb-6 md:px-6">
          <Rail />
          <main className={cn("min-w-0 flex-1", !fullBleed && "pb-2")}>
            <Outlet />
            {!fullBleed && <footer className="no-print mt-8 text-[0.7rem] text-muted-foreground">{branding?.disclaimer}</footer>}
          </main>
        </div>
      </div>
    </CommandPaletteProvider>
  );
}
