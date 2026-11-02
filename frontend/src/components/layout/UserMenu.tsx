import { useQueryClient } from "@tanstack/react-query";
import { LogOut, Monitor, Moon, Palette, Settings, Sun, User as UserIcon } from "lucide-react";
import { useNavigate } from "react-router";
import { useMe } from "@/api/hooks";
import { useAppearance } from "@/app/appearance";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuRadioGroup, DropdownMenuRadioItem,
  DropdownMenuSeparator, DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger, DropdownMenuTrigger,
} from "@/components/ui";
import { api } from "@/lib/api";
import { initials } from "@/lib/utils";

export function UserMenu() {
  const { data: me } = useMe();
  const { appearance, update } = useAppearance();
  const navigate = useNavigate();
  const qc = useQueryClient();
  if (!me) return null;
  const logout = async () => {
    await api("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    qc.clear();
    navigate("/login", { replace: true });
  };
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex size-10 items-center justify-center rounded-xl bg-primary text-[0.8rem] font-semibold text-primary-foreground shadow-card ring-2 ring-white/60 transition-transform hover:scale-[1.03] dark:ring-white/10" aria-label="Account menu">
          {initials(me.full_name)}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-60">
        <DropdownMenuLabel>
          <div className="text-sm font-medium text-foreground">{me.title ? `${me.title} ` : ""}{me.full_name.replace(/^Dr\.?\s+/, "")}</div>
          <div className="truncate">{me.email}</div>
          <div className="mt-0.5 capitalize">{me.role}{me.specialty ? ` · ${me.specialty}` : ""}</div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate("/settings/profile")}><UserIcon /> Profile</DropdownMenuItem>
        <DropdownMenuItem onSelect={() => navigate("/settings/appearance")}><Palette /> Appearance</DropdownMenuItem>
        <DropdownMenuSub>
          <DropdownMenuSubTrigger>{appearance.theme === "dark" ? <Moon /> : appearance.theme === "system" ? <Monitor /> : <Sun />} Theme</DropdownMenuSubTrigger>
          <DropdownMenuSubContent>
            <DropdownMenuRadioGroup value={appearance.theme} onValueChange={(v) => update({ theme: v as "light" | "dark" | "system" })}>
              <DropdownMenuRadioItem value="light">Light</DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="dark">Dark</DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="system">System</DropdownMenuRadioItem>
            </DropdownMenuRadioGroup>
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        <DropdownMenuItem onSelect={() => navigate("/settings")}><Settings /> Settings</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem danger onSelect={logout}><LogOut /> Sign out</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export { initials };
