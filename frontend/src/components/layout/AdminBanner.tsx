import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { Link } from "react-router";
import { api } from "@/lib/api";

/** Shown to administrators only, when the licence or the backups need attention. Never blocks anything. */
export function AdminBanner() {
  const { data: lic } = useQuery({ queryKey: ["licence"], queryFn: () => api<{ mode: string; message: string; enforced: boolean }>("/api/system/licence"), staleTime: 300000 });
  const { data: bk } = useQuery({ queryKey: ["backup"], queryFn: () => api<{ last_ok_at?: string; supported: boolean }>("/api/system/backup"), staleTime: 300000 });
  const stale = bk?.supported && (!bk.last_ok_at || Date.now() - new Date(bk.last_ok_at).getTime() > 36 * 3600 * 1000);
  const licenceProblem = lic && lic.enforced && ["grace", "expired", "invalid"].includes(lic.mode);
  const items = [
    licenceProblem ? { to: "/settings/licence", text: lic!.message } : null,
    stale ? { to: "/settings/backup", text: bk?.last_ok_at ? "The last backup is more than a day and a half old." : "No backup has been taken yet." } : null,
  ].filter(Boolean) as { to: string; text: string }[];
  if (!items.length) return null;
  return (
    <div className="no-print mb-3 space-y-1.5">
      {items.map((i) => (
        <Link key={i.to} to={i.to} className="flex items-center gap-2 rounded-lg border border-warning/40 bg-warning-soft/60 px-3 py-2 text-sm hover:bg-warning-soft">
          <AlertTriangle className="size-4 shrink-0 text-warning" /> {i.text} <span className="ml-auto text-xs font-semibold text-primary">Open</span>
        </Link>
      ))}
    </div>
  );
}
