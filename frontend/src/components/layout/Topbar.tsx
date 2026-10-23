import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Menu, MessageSquarePlus, Moon, Plus, Search, Sun, Upload, UserPlus } from "lucide-react";
import { useState } from "react";
import { NavLink, useNavigate } from "react-router";
import { useMe } from "@/api/hooks";
import { useAppearance } from "@/app/appearance";
import { Button, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, Kbd, SheetContent, Tooltip } from "@/components/ui";
import { cn } from "@/lib/utils";
import { BrandMark } from "./BrandMark";
import { usePalette } from "./CommandPalette";
import { NAV } from "./nav";

export function Topbar() {
  const palette = usePalette();
  const { resolvedTheme, update } = useAppearance();
  const { data: me } = useMe();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const isMac = typeof navigator !== "undefined" && /Mac/i.test(navigator.platform);

  return (
    <header className="no-print sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur-md md:px-6">
      <DialogPrimitive.Root open={mobileOpen} onOpenChange={setMobileOpen}>
        <DialogPrimitive.Trigger asChild>
          <Button variant="ghost" size="icon-sm" className="md:hidden" aria-label="Open navigation"><Menu /></Button>
        </DialogPrimitive.Trigger>
        <SheetContent title={<BrandMark />} width="max-w-[280px] left-0 right-auto border-l-0 border-r">
          <nav className="space-y-4 p-3">
            {NAV.map((g) => (
              <div key={g.group}>
                <div className="text-label mb-1 px-2">{g.group}</div>
                {g.items.filter((i) => !i.roles || (me && i.roles.includes(me.role))).map((i) => (
                  <NavLink key={i.to} to={i.to} end={i.to === "/"} onClick={() => setMobileOpen(false)} className={({ isActive }) => cn("flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium", isActive ? "bg-primary-soft text-primary-soft-foreground" : "hover:bg-muted")}>
                    <i.icon className="size-4" /> {i.label}
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
        </SheetContent>
      </DialogPrimitive.Root>

      <button
        onClick={palette.open}
        className="group flex h-9 w-full max-w-md items-center gap-2 rounded-lg border bg-card px-3 text-left text-sm text-muted-foreground shadow-xs transition-colors hover:border-input hover:text-foreground"
      >
        <Search className="size-4" />
        <span className="flex-1 truncate">Search patients, pages, actions…</span>
        <span className="hidden items-center gap-0.5 sm:flex"><Kbd>{isMac ? "⌘" : "Ctrl"}</Kbd><Kbd>K</Kbd></span>
      </button>

      <div className="ml-auto flex items-center gap-1.5">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="sm" className="hidden sm:inline-flex"><Plus /> New</Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-56">
            {me?.role !== "viewer" && <DropdownMenuItem onSelect={() => navigate("/patients?new=1")}><UserPlus /> Patient</DropdownMenuItem>}
            <DropdownMenuItem onSelect={() => navigate("/assistant?new=1")}><MessageSquarePlus /> Conversation</DropdownMenuItem>
            {me?.role === "admin" && <DropdownMenuItem onSelect={() => navigate("/library?upload=1")}><Upload /> Library document</DropdownMenuItem>}
          </DropdownMenuContent>
        </DropdownMenu>
        <Tooltip content={resolvedTheme === "dark" ? "Light theme" : "Dark theme"}>
          <Button variant="ghost" size="icon-sm" onClick={() => update({ theme: resolvedTheme === "dark" ? "light" : "dark" })} aria-label="Toggle theme">
            {resolvedTheme === "dark" ? <Sun /> : <Moon />}
          </Button>
        </Tooltip>
      </div>
    </header>
  );
}
