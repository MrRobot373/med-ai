import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { NavLink } from "react-router";
import { useInbox, useMe } from "@/api/hooks";
import { useAppearance } from "@/app/appearance";
import { Tooltip } from "@/components/ui";
import { cn } from "@/lib/utils";
import { BrandMark } from "./BrandMark";
import { NAV } from "./nav";
import { StatusIndicator } from "./StatusIndicator";
import { UserMenu } from "./UserMenu";

export function Sidebar() {
  const { appearance, update } = useAppearance();
  const collapsed = appearance.sidebar_collapsed;
  const { data: me } = useMe();
  const { data: inbox } = useInbox();
  const inboxCount = inbox?.filter((i) => i.priority !== "low").length ?? 0;

  return (
    <aside className={cn("no-print sticky top-0 hidden h-screen shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200 md:flex", collapsed ? "w-[64px]" : "w-[248px]")}>
      <div className={cn("flex h-14 items-center border-b border-sidebar-border px-3", collapsed && "justify-center px-0")}>
        <BrandMark showText={!collapsed} />
      </div>
      <nav className="flex-1 space-y-5 overflow-y-auto px-2.5 py-4">
        {NAV.map((group) => {
          const items = group.items.filter((i) => !i.roles || (me && i.roles.includes(me.role)));
          if (!items.length) return null;
          return (
            <div key={group.group}>
              {!collapsed && <div className="text-label mb-1.5 px-2.5 !text-[0.66rem]">{group.group}</div>}
              <div className="space-y-0.5">
                {items.map((item) => (
                  <Tooltip key={item.to} content={collapsed ? item.label : undefined} side="right">
                    <NavLink
                      to={item.to}
                      end={item.to === "/"}
                      className={({ isActive }) =>
                        cn(
                          "group relative flex h-9 items-center gap-2.5 rounded-md px-2.5 text-[0.85rem] font-medium text-sidebar-foreground transition-colors hover:bg-sidebar-active hover:text-foreground",
                          isActive && "bg-primary-soft text-primary-soft-foreground hover:bg-primary-soft hover:text-primary-soft-foreground",
                          collapsed && "justify-center px-0",
                        )
                      }
                    >
                      <item.icon className="size-[18px] shrink-0" strokeWidth={1.85} />
                      {!collapsed && <span className="truncate">{item.label}</span>}
                      {item.badge === "inbox" && inboxCount > 0 && (
                        <span className={cn("ml-auto rounded-full bg-danger px-1.5 text-[0.65rem] font-semibold leading-[1.15rem] text-white num", collapsed && "absolute right-1.5 top-1 px-1 leading-4")}>
                          {inboxCount > 99 ? "99+" : inboxCount}
                        </span>
                      )}
                    </NavLink>
                  </Tooltip>
                ))}
              </div>
            </div>
          );
        })}
      </nav>
      <div className="space-y-1 border-t border-sidebar-border p-2.5">
        <StatusIndicator collapsed={collapsed} />
        <UserMenu collapsed={collapsed} />
        <button
          onClick={() => update({ sidebar_collapsed: !collapsed })}
          className={cn("flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-xs text-muted-foreground hover:bg-sidebar-active hover:text-foreground", collapsed && "justify-center px-0")}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <PanelLeftOpen className="size-4" /> : <><PanelLeftClose className="size-4" /> Collapse</>}
        </button>
      </div>
    </aside>
  );
}
