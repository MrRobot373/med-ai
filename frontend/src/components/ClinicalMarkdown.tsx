import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

const CITATION_PATTERN = /\[([PLW]\d+)\]/g;

/** Rewrites `[P1]`/`[L2]`/`[W3]`-style evidence markers into markdown links pointing at
 * a `#cite-` fragment, so react-markdown's normal link machinery renders them — instead
 * of leaving them as literal bracketed text once real markdown rendering is turned on. */
function linkifyCitations(text: string): string {
  return text.replace(CITATION_PATTERN, (_match, label: string) => `[${label}](#cite-${label})`);
}

const components: Components = {
  // Citation links get a badge; anything else (e.g. a real http(s) URL from the model)
  // opens normally rather than being swallowed by the citation styling.
  a({ href, children, ...props }) {
    if (href?.startsWith("#cite-")) {
      const label = href.slice("#cite-".length);
      return (
        <button
          type="button"
          onClick={() => document.getElementById(`evidence-${label}`)?.scrollIntoView({ behavior: "smooth", block: "center" })}
          className="mx-0.5 inline-flex rounded bg-light-blue px-1 text-[11px] font-semibold text-primary-blue hover:bg-primary-blue hover:text-white"
        >
          {label}
        </button>
      );
    }
    return (
      <a href={href} target="_blank" rel="noreferrer" className="underline decoration-dotted underline-offset-2" {...props}>
        {children}
      </a>
    );
  },
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  h1: ({ children }) => <h4 className="mb-1.5 mt-3 text-sm font-bold first:mt-0">{children}</h4>,
  h2: ({ children }) => <h4 className="mb-1.5 mt-3 text-sm font-bold first:mt-0">{children}</h4>,
  h3: ({ children }) => <h4 className="mb-1.5 mt-3 text-sm font-semibold first:mt-0">{children}</h4>,
  code: ({ children }) => <code className="rounded bg-black/5 px-1 py-0.5 text-[13px]">{children}</code>,
  table: ({ children }) => (
    <div className="mb-2 overflow-x-auto last:mb-0">
      <table className="min-w-full border-collapse text-xs">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border border-border px-2 py-1 text-left font-semibold">{children}</th>,
  td: ({ children }) => <td className="border border-border px-2 py-1">{children}</td>,
};

/** Renders model/report-generated clinical text as real markdown (bold, bullets,
 * headings, tables) instead of showing the raw `**`/`*`/`#` syntax verbatim, while still
 * turning `[P1]`/`[L2]`/`[W3]` evidence markers into the same clickable badges the plain
 * citation renderer used to produce. Use this anywhere generated text is displayed —
 * Clinical AI chat, Guideline Q&A, Research, and the structured clinical modules. */
export function ClinicalMarkdown({ text, className }: { text: string; className?: string }) {
  return (
    <div className={`text-sm leading-relaxed ${className ?? ""}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {linkifyCitations(text)}
      </ReactMarkdown>
    </div>
  );
}
