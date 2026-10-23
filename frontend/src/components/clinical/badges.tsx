import { AlertTriangle, CheckCircle2, CircleDashed, Clock, Loader2, ShieldAlert, ShieldCheck, ShieldQuestion, TrendingDown, TrendingUp, XCircle } from "lucide-react";
import { Badge } from "@/components/ui";
import { titleCase } from "@/lib/utils";

export function DocStatusBadge({ status }: { status: string }) {
  if (status === "processing") return <Badge tone="info"><Loader2 className="animate-spin" /> Processing</Badge>;
  if (status === "ready") return <Badge tone="success"><CheckCircle2 /> Ready</Badge>;
  if (status === "failed") return <Badge tone="danger"><XCircle /> Failed</Badge>;
  return <Badge>{titleCase(status)}</Badge>;
}

export function IdentityBadge({ status, detail }: { status: string; detail?: string | null }) {
  if (status === "n/a") return null;
  if (status === "match") return <Badge tone="success" title={detail ?? ""}><ShieldCheck /> Identity verified</Badge>;
  if (status === "mismatch") return <Badge tone="danger" title={detail ?? ""}><ShieldAlert /> Wrong patient?</Badge>;
  return <Badge tone="warning" title={detail ?? ""}><ShieldQuestion /> Unverified</Badge>;
}

export function ReviewBadge({ status }: { status: string }) {
  return status === "reviewed" ? <Badge tone="neutral"><CheckCircle2 /> Reviewed</Badge> : <Badge tone="primary"><Clock /> To review</Badge>;
}

export function FlagBadge({ flag, compact }: { flag: string | null; compact?: boolean }) {
  if (!flag) return compact ? null : <Badge tone="outline"><CircleDashed /> No range</Badge>;
  if (flag === "high") return <Badge tone="danger"><TrendingUp /> High</Badge>;
  if (flag === "low") return <Badge tone="warning"><TrendingDown /> Low</Badge>;
  if (flag === "abnormal") return <Badge tone="danger"><AlertTriangle /> Abnormal</Badge>;
  return compact ? null : <Badge tone="success">Normal</Badge>;
}

export function RunStatusBadge({ status }: { status: string }) {
  const tone = { draft: "primary", accepted: "success", discarded: "neutral", error: "danger" }[status] as any;
  return <Badge tone={tone}>{status === "draft" ? "Draft — needs review" : titleCase(status)}</Badge>;
}

export const SEVERITY_TONE: Record<string, "danger" | "warning" | "neutral"> = { severe: "danger", moderate: "warning", mild: "neutral", unknown: "neutral" };
