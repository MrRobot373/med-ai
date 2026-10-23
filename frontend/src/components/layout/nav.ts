import { BookOpenText, Globe, Home, Inbox, MessagesSquare, ScrollText, Settings, Stethoscope, Users, type LucideIcon } from "lucide-react";
import type { Role } from "@/api/types";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  roles?: Role[];
  badge?: "inbox";
  shortcut?: string;
}

/** Centre pill navigation — the clinical workspace. */
export const PRIMARY_NAV: NavItem[] = [
  { to: "/", label: "Dashboard", icon: Home, shortcut: "G H" },
  { to: "/patients", label: "Patients", icon: Users, shortcut: "G P" },
  { to: "/assistant", label: "Assistant", icon: MessagesSquare, shortcut: "G A" },
  { to: "/inbox", label: "Inbox", icon: Inbox, badge: "inbox", shortcut: "G I" },
];

/** Left icon rail — tools and administration. */
export const RAIL_NAV: NavItem[] = [
  { to: "/tools", label: "Clinical tools", icon: Stethoscope },
  { to: "/research", label: "Research", icon: Globe },
  { to: "/library", label: "Knowledge library", icon: BookOpenText, shortcut: "G L" },
  { to: "/audit", label: "Audit log", icon: ScrollText, roles: ["admin"] },
  { to: "/settings", label: "Settings", icon: Settings, shortcut: "G S" },
];

export const NAV: { group: string; items: NavItem[] }[] = [
  { group: "Workspace", items: PRIMARY_NAV },
  { group: "Tools & administration", items: RAIL_NAV },
];
