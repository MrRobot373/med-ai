import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";

// Mirrors backend/app/schemas/health.py — keep these in sync when the schema changes.
export interface OllamaStatus {
  reachable: boolean;
  version: string | null;
  configured_model: string;
  model_available: boolean;
  error: string | null;
}

export interface QdrantStatus {
  reachable: boolean;
  collections: string[];
  error: string | null;
}

export interface DatabaseStatus {
  reachable: boolean;
  error: string | null;
}

export interface OverallHealth {
  status: "ok" | "degraded";
  backend: boolean;
  database: DatabaseStatus;
  ollama: OllamaStatus;
  qdrant: QdrantStatus;
}

export function useSystemHealth() {
  return useQuery({
    queryKey: ["health", "overall"],
    queryFn: () => apiFetch<OverallHealth>("/api/health"),
    // Health drives the header status chip — keep it fresh without hammering the
    // backend on every render.
    refetchInterval: 30_000,
    retry: 1,
  });
}
