import { useState } from "react";
import { ClipboardList, Lock, MessageSquare } from "lucide-react";
import { Card } from "@/components/Card";
import { useIsAdmin } from "@/api/auth";
import { AUDIT_ACTION_LABELS, useAuditLogs, type AuditAction, type AuditOutcome } from "@/api/audit";
import { FEEDBACK_RATING_LABELS, useAdminFeedback, type FeedbackRating, type FeedbackTarget } from "@/api/feedback";
import { relativeTime } from "@/pages/PatientWorkspace/ClinicalModules/shared";

const OUTCOME_STYLE: Record<AuditOutcome, string> = {
  success: "bg-success/10 text-success",
  failure: "bg-danger/10 text-danger",
};

function AuditLogTab() {
  const [action, setAction] = useState<AuditAction | "">("");
  const [outcome, setOutcome] = useState<AuditOutcome | "">("");
  const { data: rows, isLoading } = useAuditLogs({
    action: action || undefined,
    outcome: outcome || undefined,
  });

  return (
    <Card className="space-y-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={action}
          onChange={(e) => setAction(e.target.value as AuditAction | "")}
          className="rounded-md border border-border px-2 py-1.5 text-sm"
        >
          <option value="">All actions</option>
          {Object.entries(AUDIT_ACTION_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          value={outcome}
          onChange={(e) => setOutcome(e.target.value as AuditOutcome | "")}
          className="rounded-md border border-border px-2 py-1.5 text-sm"
        >
          <option value="">Any outcome</option>
          <option value="success">Success</option>
          <option value="failure">Failure</option>
        </select>
      </div>

      {isLoading && <p className="text-sm text-muted-text">Loading audit log…</p>}
      {!isLoading && rows?.length === 0 && <p className="text-sm text-muted-text">No matching audit events yet.</p>}

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-border text-muted-text">
              <th className="py-1.5 pr-3 font-medium">When</th>
              <th className="py-1.5 pr-3 font-medium">User</th>
              <th className="py-1.5 pr-3 font-medium">Action</th>
              <th className="py-1.5 pr-3 font-medium">Object</th>
              <th className="py-1.5 font-medium">Outcome</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows?.map((row) => (
              <tr key={row.id}>
                <td className="py-1.5 pr-3 whitespace-nowrap text-muted-text">{relativeTime(row.created_at)}</td>
                <td className="py-1.5 pr-3 text-navy">{row.user_email ?? "—"}</td>
                <td className="py-1.5 pr-3 text-navy">{AUDIT_ACTION_LABELS[row.action]}</td>
                <td className="py-1.5 pr-3 text-muted-text">
                  {row.object_type ? `${row.object_type}${row.object_id ? ` · ${row.object_id.slice(0, 8)}` : ""}` : "—"}
                </td>
                <td className="py-1.5">
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${OUTCOME_STYLE[row.outcome]}`}>
                    {row.outcome.toUpperCase()}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function FeedbackTab() {
  const [rating, setRating] = useState<FeedbackRating | "">("");
  const [targetType, setTargetType] = useState<FeedbackTarget | "">("");
  const { data: rows, isLoading } = useAdminFeedback({
    rating: rating || undefined,
    targetType: targetType || undefined,
  });

  return (
    <Card className="space-y-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={rating}
          onChange={(e) => setRating(e.target.value as FeedbackRating | "")}
          className="rounded-md border border-border px-2 py-1.5 text-sm"
        >
          <option value="">All ratings</option>
          {Object.entries(FEEDBACK_RATING_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          value={targetType}
          onChange={(e) => setTargetType(e.target.value as FeedbackTarget | "")}
          className="rounded-md border border-border px-2 py-1.5 text-sm"
        >
          <option value="">All surfaces</option>
          <option value="message">Clinical AI chat</option>
          <option value="clinical_module_run">Clinical modules / Research</option>
        </select>
      </div>

      {isLoading && <p className="text-sm text-muted-text">Loading feedback…</p>}
      {!isLoading && rows?.length === 0 && <p className="text-sm text-muted-text">No feedback submitted yet.</p>}

      <div className="space-y-2">
        {rows?.map((row) => (
          <div key={row.id} className="rounded-md border border-border p-2.5 text-xs">
            <div className="flex items-center justify-between gap-2">
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                  row.rating === "helpful" ? "bg-success/10 text-success" : "bg-danger/10 text-danger"
                }`}
              >
                {FEEDBACK_RATING_LABELS[row.rating]}
              </span>
              <span className="text-muted-text">{relativeTime(row.created_at)}</span>
            </div>
            <div className="mt-1 text-muted-text">
              {row.target_type === "message" ? "Clinical AI chat" : "Clinical module / Research"} · {row.target_id.slice(0, 8)}
            </div>
            {row.comment && <p className="mt-1 text-navy">&ldquo;{row.comment}&rdquo;</p>}
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function AuditPage() {
  const isAdmin = useIsAdmin();
  const [tab, setTab] = useState<"audit" | "feedback">("audit");

  if (!isAdmin) {
    return (
      <Card className="mx-auto max-w-2xl p-6 text-center text-sm text-muted-text">
        <Lock className="mx-auto mb-2 h-5 w-5 text-muted-text" />
        <p className="font-medium text-navy">Audit &amp; Feedback review requires an admin account.</p>
        <p className="mt-1">Spec §18 lists "Review audits" only under Admin's permissions.</p>
      </Card>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex items-center gap-2">
        <ClipboardList className="h-5 w-5 text-primary-blue" />
        <h1 className="text-lg font-semibold text-navy">Audit &amp; Feedback</h1>
      </div>
      <p className="text-sm text-muted-text">
        A record of meaningful account/clinical actions (spec §82) and clinician reactions to AI-generated answers
        (spec §81) — never raw clinical free text, only who did what and when.
      </p>

      <div className="flex gap-1 border-b border-border">
        <button
          type="button"
          onClick={() => setTab("audit")}
          className={`inline-flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium ${
            tab === "audit" ? "border-primary-blue text-primary-blue" : "border-transparent text-muted-text hover:text-navy"
          }`}
        >
          <ClipboardList className="h-3.5 w-3.5" />
          Audit Log
        </button>
        <button
          type="button"
          onClick={() => setTab("feedback")}
          className={`inline-flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium ${
            tab === "feedback" ? "border-primary-blue text-primary-blue" : "border-transparent text-muted-text hover:text-navy"
          }`}
        >
          <MessageSquare className="h-3.5 w-3.5" />
          Feedback
        </button>
      </div>

      {tab === "audit" ? <AuditLogTab /> : <FeedbackTab />}
    </div>
  );
}
