import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";

export type SettingsView = Record<string, any> & { index_status: { reindex_required: boolean; dimension: number | null; current_signature: string; indexed_signature: string | null }; profiles: Record<string, Record<string, number>> };

export const useSettingsView = () => useQuery({ queryKey: ["settings"], queryFn: () => api<SettingsView>("/api/settings") });

const SECRET_KEYS = ["api_key", "pubmed_api_key"];

/** Draft state for one admin settings section with dirty tracking, save and test. */
export function useSection(section: string) {
  const { data, isLoading } = useSettingsView();
  const qc = useQueryClient();
  const server = data?.[section] as Record<string, any> | undefined;
  const [draft, setDraft] = useState<Record<string, any>>({});
  const [secrets, setSecrets] = useState<Record<string, string | null>>({});
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<Record<string, any> | null>(null);

  useEffect(() => { if (server) { setDraft(server); setSecrets({}); } }, [server]);

  const dirty = useMemo(() => {
    if (!server) return false;
    // "" means "replace box open but empty" — not a change; null means "remove".
    if (Object.values(secrets).some((v) => v === null || !!v)) return true;
    return Object.keys(draft).some((k) => !k.startsWith("has_") && !k.endsWith("_preview") && JSON.stringify(draft[k]) !== JSON.stringify(server[k]));
  }, [draft, server, secrets]);

  const payload = () => {
    const body: Record<string, any> = {};
    for (const [k, v] of Object.entries(draft)) if (!k.startsWith("has_") && !k.endsWith("_preview") && !SECRET_KEYS.includes(k)) body[k] = v;
    for (const [k, v] of Object.entries(secrets)) {
      if (v === null) body[k] = "";
      else if (v) body[k] = v;
    }
    return body;
  };

  const set = (patch: Record<string, any>) => setDraft((d) => ({ ...d, ...patch }));
  const setSecret = (key: string, value: string | null | undefined) => setSecrets((s) => {
    const next = { ...s };
    if (value === undefined) delete next[key]; else next[key] = value;
    return next;
  });

  const save = async () => {
    setSaving(true);
    try {
      const view = await api<SettingsView>(`/api/settings/${section}`, { method: "PUT", body: payload() });
      qc.setQueryData(["settings"], (old: SettingsView | undefined) => ({ ...(old ?? {}), ...view, profiles: old?.profiles ?? {} }));
      qc.invalidateQueries({ queryKey: ["health"] });
      if (section === "branding") qc.invalidateQueries({ queryKey: ["branding"] });
      toast.success("Settings saved", { description: "Changes apply to the next request — no restart needed." });
      return view;
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not save");
    } finally {
      setSaving(false);
    }
  };

  const test = async (component = section) => {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await api(`/api/settings/test/${component}`, { method: "POST", body: { overrides: payload() } }));
    } catch (e) {
      setTestResult({ ok: false, error: e instanceof ApiError ? e.message : "Test failed" });
    } finally {
      setTesting(false);
    }
  };

  const reset = () => { if (server) { setDraft(server); setSecrets({}); } };
  return { data, server, draft, set, secrets, setSecret, dirty, save, saving, test, testing, testResult, setTestResult, reset, isLoading };
}
