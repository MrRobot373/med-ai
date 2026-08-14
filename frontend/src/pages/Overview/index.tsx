import { useSystemHealth } from "@/api/health";
import { StatusChip, type StatusTone } from "@/components/StatusChip";

function toneFor(reachable: boolean | undefined, isLoading: boolean): StatusTone {
  if (isLoading) return "loading";
  return reachable ? "ok" : "down";
}

/**
 * Phase 01 Overview: real, live-checked service status only. The full marketing hero /
 * capability cards / clinician dashboard metrics from spec §22 land in Phase 02 (UI
 * shell) and Phase 04+ (once there is real patient data to summarize) — this page does
 * not fabricate those numbers in the meantime.
 */
export default function OverviewPage() {
  const { data, isLoading, isError, error } = useSystemHealth();

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-navy">System Status</h1>
        <p className="text-sm text-muted-text">
          Live health of the local clinical AI stack. Nothing on this page is simulated.
        </p>
      </div>

      {isError && (
        <div className="gms-card border-danger/30 bg-danger/5 p-4 text-sm text-danger">
          Could not reach the backend at all: {(error as Error).message}. Is it running on
          the configured port?
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="gms-card p-4">
          <div className="mb-2 text-sm font-medium text-navy">Database</div>
          <StatusChip
            label={isLoading ? "Checking…" : data?.database.reachable ? "Ready" : "Unreachable"}
            tone={toneFor(data?.database.reachable, isLoading)}
          />
        </div>

        <div className="gms-card p-4">
          <div className="mb-2 text-sm font-medium text-navy">Local AI (Ollama)</div>
          <StatusChip
            label={
              isLoading
                ? "Checking…"
                : data?.ollama.reachable
                  ? data.ollama.model_available
                    ? "Ready"
                    : "Model missing"
                  : "Unreachable"
            }
            tone={
              isLoading
                ? "loading"
                : !data?.ollama.reachable
                  ? "down"
                  : data.ollama.model_available
                    ? "ok"
                    : "degraded"
            }
          />
          {data?.ollama.error && <p className="mt-2 text-xs text-muted-text">{data.ollama.error}</p>}
        </div>

        <div className="gms-card p-4">
          <div className="mb-2 text-sm font-medium text-navy">Vector Index (Qdrant)</div>
          <StatusChip
            label={isLoading ? "Checking…" : data?.qdrant.reachable ? "Ready" : "Unreachable"}
            tone={toneFor(data?.qdrant.reachable, isLoading)}
          />
          {data?.qdrant.error && <p className="mt-2 text-xs text-muted-text">{data.qdrant.error}</p>}
        </div>
      </div>

      <div className="gms-card p-4 text-xs text-muted-text">
        Clinical Decision Support — evidence and generated content must be reviewed by
        the treating clinician.
      </div>
    </div>
  );
}
