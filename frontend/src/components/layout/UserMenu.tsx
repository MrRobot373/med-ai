import { useQueryClient } from "@tanstack/react-query";
import { LogOut, Monitor, Moon, Palette, Settings, Sun, User as UserIcon } from "lucide-react";
import { useNavigate } from "react-router";
import { useMe } from "@/api/hooks";
import { useAppearance } from "@/app/appearance";
import {
  Avatar, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuRadioGroup, DropdownMenuRadioItem,
  DropdownMenuSeparator, DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger, DropdownMenuTrigger,
} from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export function UserMenu({ collapsed }: { collapsed?: boolean }) {
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
  const display = `${me.title ? me.title + " " : ""}${me.full_name.replace(/^Dr\.?\s+/, me.title ? "" : "Dr. ")}`.trim();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className={cn("flex w-full items-center gap-2.5 rounded-lg p-1.5 text-left transition-colors hover:bg-sidebar-active", collapsed && "justify-center")}>
          <Avatar name={me.full_name} size="sm" />
          {!collapsed && (
            <div className="min-w-0 flex-1 leading-tight">
              <div className="truncate text-[0.8rem] font-medium">{display}</div>
              <div className="truncate text-[0.7rem] capitalize text-muted-foreground">{me.role}{me.specialty ? ` · ${me.specialty}` : ""}</div>
            </div>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="right" align="end" className="w-60">
        <DropdownMenuLabel>
          <div className="text-sm font-medium text-foreground">{me.full_name}</div>
          <div className="truncate">{me.email}</div>
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
