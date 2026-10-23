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

const CLINICAL: Role[] = ["admin", "clinician", "viewer"];

/** Centre pill navigation — the clinical workspace. */
export const PRIMARY_NAV: NavItem[] = [
  { to: "/", label: "Dashboard", icon: Home, shortcut: "G H" },
  { to: "/patients", label: "Patients", icon: Users, shortcut: "G P" },
  { to: "/assistant", label: "Assistant", icon: MessagesSquare, shortcut: "G A", roles: CLINICAL },
  { to: "/inbox", label: "Inbox", icon: Inbox, badge: "inbox", shortcut: "G I", roles: CLINICAL },
];

/** Left icon rail — tools and administration. */
export const RAIL_NAV: NavItem[] = [
  { to: "/tools", label: "Clinical tools", icon: Stethoscope, roles: CLINICAL },
  { to: "/research", label: "Research", icon: Globe, roles: CLINICAL },
  { to: "/library", label: "Knowledge library", icon: BookOpenText, shortcut: "G L", roles: CLINICAL },
  { to: "/audit", label: "Audit log", icon: ScrollText, roles: ["admin"] },
  { to: "/settings", label: "Settings", icon: Settings, shortcut: "G S" },
];

export const visibleFor = (items: NavItem[], role?: Role) => items.filter((i) => !i.roles || (role && i.roles.includes(role)));

export const NAV: { group: string; items: NavItem[] }[] = [
  { group: "Workspace", items: PRIMARY_NAV },
  { group: "Tools & administration", items: RAIL_NAV },
];
