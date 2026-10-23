import { Activity, RefreshCw } from "lucide-react";
import { Link } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useHealth } from "@/api/hooks";
import { api } from "@/lib/api";
import { Badge, Button, Dot, Popover, PopoverContent, PopoverTrigger, Tooltip } from "@/components/ui";
import { cn, fmtRelative } from "@/lib/utils";
import type { HealthComponent } from "@/api/types";

const LABELS: Record<string, string> = {
  database: "Database", llm: "Language model", embeddings: "Embeddings", reranker: "Reranker", vector_store: "Vector store", research: "Web research",
};
export const STATUS_TONE = { online: "success", degraded: "warning", offline: "danger", disabled: "neutral" } as const;

export function ComponentRow({ c }: { c: HealthComponent }) {
  return (
    <div className="flex items-start gap-2.5 py-1.5">
      <Dot tone={STATUS_TONE[c.status]} className="mt-1.5" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[0.8rem] font-medium">{LABELS[c.component] ?? c.component}</span>
          <span className="text-[0.7rem] capitalize text-muted-foreground">{c.status}</span>
        </div>
        <p className={cn("truncate text-xs", c.error ? "text-danger" : "text-muted-foreground")} title={c.error ?? c.detail}>{c.error ?? c.detail}</p>
      </div>
    </div>
  );
}

export function StatusIndicator({ collapsed }: { collapsed?: boolean }) {
  const { data, isFetching } = useHealth();
  const qc = useQueryClient();
  const status = data?.status ?? "degraded";
  const label = { online: "All systems operational", degraded: "Degraded", offline: "AI services offline" }[status];
  const refresh = async () => {
    qc.setQueryData(["health"], await api("/api/system/health", { query: { refresh: true } }));
  };
  return (
    <Popover>
      <Tooltip content={collapsed ? label : undefined} side="right">
        <PopoverTrigger asChild>
          <button className={cn("flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-xs text-sidebar-foreground transition-colors hover:bg-sidebar-active", collapsed && "justify-center px-0")}>
            <Dot tone={data ? STATUS_TONE[status] : "neutral"} pulse={status === "online"} />
            {!collapsed && <span className="truncate">{data ? label : "Checking services…"}</span>}
          </button>
        </PopoverTrigger>
      </Tooltip>
      <PopoverContent side="right" align="end" className="w-80 p-0">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold"><Activity className="size-4 text-primary" /> System status</div>
            <div className="text-xs text-muted-foreground">Checked {fmtRelative(data?.checked_at)}</div>
          </div>
          <Badge tone={STATUS_TONE[status]} className="capitalize">{status}</Badge>
        </div>
        <div className="px-4 py-2">{data?.components.map((c) => <ComponentRow key={c.component} c={c} />)}</div>
        <div className="flex items-center justify-between border-t bg-subtle px-4 py-2.5">
          <Button size="xs" variant="ghost" onClick={refresh} loading={isFetching}><RefreshCw /> Re-check</Button>
          <Button size="xs" variant="link" asChild><Link to="/settings/system">Details</Link></Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
