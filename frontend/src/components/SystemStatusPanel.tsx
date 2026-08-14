import { useSystemHealth } from "@/api/health";
import { Card } from "@/components/Card";
import { StatusChip, type StatusTone } from "@/components/StatusChip";

function toneFor(reachable: boolean | undefined, isLoading: boolean): StatusTone {
  if (isLoading) return "loading";
  return reachable ? "ok" : "down";
}

/**
 * Real, live-checked service status (spec §84) — nothing here is simulated. Extracted
 * from the Phase 01 Overview page so it can be reused/positioned independently as the
 * rest of the dashboard (spec §22) is built around it.
 */
export function SystemStatusPanel() {
  const { data, isLoading, isError, error } = useSystemHealth();

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-navy">System Status</h2>
        <p className="text-sm text-muted-text">
          Live health of the local clinical AI stack. Nothing on this page is simulated.
        </p>
      </div>

      {isError && (
        <Card className="border-danger/30 bg-danger/5 p-4 text-sm text-danger">
          Could not reach the backend at all: {(error as Error).message}. Is it running on
          the configured port?
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card className="p-4">
          <div className="mb-2 text-sm font-medium text-navy">Database</div>
          <StatusChip
            label={isLoading ? "Checking…" : data?.database.reachable ? "Ready" : "Unreachable"}
            tone={toneFor(data?.database.reachable, isLoading)}
          />
        </Card>

        <Card className="p-4">
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
        </Card>

        <Card className="p-4">
          <div className="mb-2 text-sm font-medium text-navy">Vector Index (Qdrant)</div>
          <StatusChip
            label={isLoading ? "Checking…" : data?.qdrant.reachable ? "Ready" : "Unreachable"}
            tone={toneFor(data?.qdrant.reachable, isLoading)}
          />
          {data?.qdrant.error && <p className="mt-2 text-xs text-muted-text">{data.qdrant.error}</p>}
        </Card>
      </div>
    </div>
  );
}
