import { Children, cloneElement, Fragment, isValidElement, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

const CITE = /\[((?:[PKW]\d{1,3}|R)(?:\s*,\s*(?:[PKW]\d{1,3}|R))*)\]/g;

function CitationChip({ label, onClick, active }: { label: string; onClick?: (l: string) => void; active?: boolean }) {
  const tone = label.startsWith("P") ? "bg-info-soft text-info-foreground" : label.startsWith("K") ? "bg-primary-soft text-primary-soft-foreground" : label.startsWith("W") ? "bg-warning-soft text-warning-foreground" : "bg-success-soft text-success-foreground";
  return (
    <button
      type="button"
      onClick={() => onClick?.(label)}
      className={cn("mx-0.5 inline-flex h-[1.15rem] -translate-y-px items-center rounded px-1 align-middle font-mono text-[0.68rem] font-semibold transition-all hover:ring-1 hover:ring-current", tone, active && "ring-1 ring-current")}
      title={label === "R" ? "Structured patient record" : `Source ${label}`}
    >
      {label}
    </button>
  );
}

function withCitations(node: ReactNode, onCite?: (l: string) => void, active?: string | null): ReactNode {
  if (typeof node === "string") {
    const parts: ReactNode[] = [];
    let last = 0;
    node.replace(CITE, (match, labels: string, offset: number) => {
      if (offset > last) parts.push(node.slice(last, offset));
      labels.split(",").map((l) => l.trim()).forEach((l, i) => parts.push(<CitationChip key={`${offset}-${i}`} label={l} onClick={onCite} active={active === l} />));
      last = offset + match.length;
      return match;
    });
    if (!parts.length) return node;
    if (last < node.length) parts.push(node.slice(last));
    return parts;
  }
  if (Array.isArray(node)) return node.map((n, i) => <Fragment key={i}>{withCitations(n, onCite, active)}</Fragment>);
  if (isValidElement<{ children?: ReactNode }>(node) && node.props.children) {
    return cloneElement(node, undefined, Children.map(node.props.children, (c) => withCitations(c, onCite, active)));
  }
  return node;
}

export function Markdown({ children, onCite, activeCitation, className }: { children: string; onCite?: (label: string) => void; activeCitation?: string | null; className?: string }) {
  const wrap = (Tag: any) => ({ children: c, node: _n, ...rest }: any) => <Tag {...rest}>{withCitations(c, onCite, activeCitation)}</Tag>;
  return (
    <div className={cn("prose-clinical", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{ p: wrap("p"), li: wrap("li"), td: wrap("td"), strong: wrap("strong"), em: wrap("em"), h1: wrap("h1"), h2: wrap("h2"), h3: wrap("h3"), a: ({ node: _n, ...p }: any) => <a {...p} target="_blank" rel="noreferrer" /> }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
