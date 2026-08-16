import type { ReactNode } from "react";
import type { ClinicalModuleRunOut } from "@/api/clinicalModules";
import { Card } from "@/components/Card";

/** A generic "N minutes/hours/days ago" — this project doesn't otherwise depend on a
 * date library, so a small local helper matches ConversationList's precedent. */
export function relativeTime(iso: string): string {
  const date = new Date(iso);
  const minutes = Math.floor((Date.now() - date.getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return date.toLocaleDateString();
}

export function Bulleted({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <ul className="list-disc space-y-0.5 pl-4 text-sm text-navy">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-text">{title}</div>
      <div className="mt-1">{children}</div>
    </div>
  );
}

export function GenerationError({ message }: { message: string }) {
  return <p className="rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">{message}</p>;
}

/** Every module type's draft-run history — a plain "when was this generated" list,
 * not an editable record (spec §63: these are drafts, never auto-finalized). */
export function RunHistoryList({ runs, moduleLabel }: { runs: ClinicalModuleRunOut[] | undefined; moduleLabel: string }) {
  const filtered = runs ?? [];
  if (filtered.length === 0) return null;
  return (
    <Card className="p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-text">Previous {moduleLabel} drafts</h3>
      <ul className="mt-2 divide-y divide-border">
        {filtered.map((run) => (
          <li key={run.id} className="flex items-center justify-between py-2 text-xs">
            <span className="text-navy">{run.generation_error ? "Failed" : "Generated"}</span>
            <span className="text-muted-text">{relativeTime(run.created_at)}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
