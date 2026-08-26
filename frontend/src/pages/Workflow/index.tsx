import { useState } from "react";
import { BookOpen } from "lucide-react";
import { Card } from "@/components/Card";
import { ApiError } from "@/api/client";
import { useCreateGuidelineQA, useGlobalRuns, type GuidelineQAPayload } from "@/api/clinicalModules";
import { useCanWrite } from "@/api/auth";
import { GenerationError, RunHistoryList } from "@/pages/PatientWorkspace/ClinicalModules/shared";
import { ClinicalMarkdown } from "@/components/ClinicalMarkdown";

const SUGGESTED_QUESTIONS = [
  "What are the diagnostic criteria for primary open-angle glaucoma?",
  "What is the recommended follow-up interval for a patient on medical glaucoma therapy?",
];

/**
 * Global Workflow page — Guideline Q&A (spec §63): strict evidence-grounded local RAG
 * over the shared knowledge base, patient-independent, its own dedicated workflow
 * rather than routed through the chat endpoint.
 */
export default function WorkflowPage() {
  const canWrite = useCanWrite();
  const [question, setQuestion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const create = useCreateGuidelineQA();
  const { data: history } = useGlobalRuns("guideline_qa");

  const payload = create.data?.payload as GuidelineQAPayload | null | undefined;

  function ask(q: string) {
    if (!q.trim()) return;
    setError(null);
    create.mutate({ question: q }, { onError: (err) => setError(err instanceof ApiError ? err.message : "Could not answer the question.") });
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex items-center gap-2">
        <BookOpen className="h-5 w-5 text-primary-blue" />
        <h1 className="text-lg font-semibold text-navy">Guideline Q&A</h1>
      </div>
      <p className="text-sm text-muted-text">
        Strictly evidence-grounded against the local knowledge base — never patient-specific, never general
        knowledge beyond what's actually indexed. If no relevant guideline exists, that's stated explicitly rather
        than answered from general knowledge.
      </p>

      <Card className="p-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(question);
          }}
          className="flex items-center gap-2"
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={!canWrite}
            placeholder={canWrite ? "Ask a guideline question…" : "Requires a doctor or admin account"}
            className="flex-1 rounded-md border border-border px-3 py-2 text-sm disabled:bg-light-blue/50"
          />
          <button
            type="submit"
            disabled={!canWrite || create.isPending || !question.trim()}
            className="rounded-md bg-primary-blue px-4 py-2 text-sm font-semibold text-white hover:bg-primary-blue/90 disabled:opacity-60"
          >
            {create.isPending ? "Asking…" : "Ask"}
          </button>
        </form>

        {canWrite && !create.data && (
          <div className="mt-3 space-y-1.5">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-text">Suggested questions</p>
            {SUGGESTED_QUESTIONS.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => ask(q)}
                className="block w-full rounded-md border border-border px-3 py-2 text-left text-sm text-navy hover:bg-light-blue"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {error && (
          <div className="mt-3">
            <GenerationError message={error} />
          </div>
        )}
      </Card>

      {payload && (
        <Card className="space-y-3 p-4">
          <ClinicalMarkdown text={payload.answer} className="text-navy" />
          {payload.citations.length > 0 && (
            <div className="space-y-2 border-t border-border pt-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-text">Sources</p>
              {payload.citations.map((c) => (
                <div key={c.label} className="rounded-md border border-border p-2 text-xs">
                  <div className="font-medium text-navy">
                    <span className="mr-1 rounded bg-light-blue px-1.5 py-0.5 text-primary-blue">{c.label}</span>
                    {c.source_title}
                    {c.page && <> · page {c.page}</>}
                    {c.section && <> · {c.section}</>}
                  </div>
                  <p className="mt-0.5 text-muted-text">&ldquo;{c.excerpt}&rdquo;</p>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      <RunHistoryList runs={history} moduleLabel="guideline Q&A" />
    </div>
  );
}
