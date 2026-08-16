import {
  BookOpen,
  Cpu,
  Database,
  FileText,
  HeartHandshake,
  MessageSquare,
  PlayCircle,
  ScanSearch,
  ServerCog,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Tags,
  Upload,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Card } from "@/components/Card";
import { CapabilityCard } from "@/components/CapabilityCard";
import { DashboardSnapshot } from "@/components/DashboardSnapshot";
import { HeroIllustration } from "@/components/HeroIllustration";
import { HowItWorksStep } from "@/components/HowItWorksStep";
import { IconBadge } from "@/components/IconBadge";
import { SystemStatusPanel } from "@/components/SystemStatusPanel";

const CAPABILITIES = [
  {
    icon: FileText,
    tone: "blue" as const,
    title: "Note Summarization",
    description: "Concise, structured summaries of clinical notes and reports.",
    to: "/clinical-ai",
  },
  {
    icon: Tags,
    tone: "green" as const,
    title: "Clinical Entity Extraction",
    description: "Identify and highlight clinical entities in patient text.",
    to: "/clinical-ai",
  },
  {
    icon: Stethoscope,
    tone: "purple" as const,
    title: "Differential Assistant",
    description: "Get differential possibilities with supporting evidence for review.",
    to: "/clinical-ai",
  },
  {
    icon: BookOpen,
    tone: "amber" as const,
    title: "Guideline Q&A",
    description: "Ask clinical questions and get evidence-backed, cited answers.",
    to: "/knowledge",
  },
  {
    icon: Database,
    tone: "cyan" as const,
    title: "EHR Reasoning",
    description: "Reason over structured patient data alongside clinical evidence.",
    to: "/patients",
  },
  {
    icon: Cpu,
    tone: "navy" as const,
    title: "Local Medical LLM",
    description: "Chat securely with a fully local model — nothing leaves this machine.",
    to: "/clinical-ai",
  },
];

const TRUST_ITEMS = [
  {
    icon: ShieldCheck,
    title: "Privacy First",
    description: "Patient data stays local and secure by default.",
  },
  {
    icon: ServerCog,
    title: "On-Premise",
    description: "Runs entirely in your own environment — no cloud dependency.",
  },
  {
    icon: HeartHandshake,
    title: "Clinician Focused",
    description: "Built around real-world clinical workflows, not a generic chatbot.",
  },
];

export default function OverviewPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-14">
      {/* Hero */}
      <section className="grid items-center gap-8 lg:grid-cols-2">
        <div>
          <h1 className="text-3xl font-bold leading-tight text-navy sm:text-4xl">
            Smarter Clinical Decisions
            <br />
            with Trusted AI
          </h1>
          <p className="mt-4 max-w-md text-muted-text">
            AI-powered tools to extract insights, summarize notes, and support better
            clinical outcomes — running entirely on local, open-source infrastructure.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-4">
            <a
              href="#capabilities"
              className="inline-flex items-center gap-2 rounded-lg bg-primary-blue px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-blue/90"
            >
              Explore Capabilities
            </a>
            {/* Spec §89 "Demo Scenarios" entry point — a distinct page (not a nav
               item, since spec §19's nav list is fixed) reachable from the landing
               page a presenter starts a demo from. */}
            <Link
              to="/demo"
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary-blue hover:underline"
            >
              <PlayCircle className="h-4 w-4" />
              Demo Scenarios
            </Link>
          </div>
        </div>
        <div className="mx-auto w-full max-w-sm">
          <HeroIllustration />
        </div>
      </section>

      {/* Capabilities + How It Works */}
      <section id="capabilities" className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <h2 className="mb-4 text-lg font-semibold text-navy">AI Capabilities</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {CAPABILITIES.map((c) => (
              <CapabilityCard key={c.title} {...c} />
            ))}
          </div>
        </div>

        <div>
          <h2 className="mb-4 text-lg font-semibold text-navy">How It Works</h2>
          <Card className="p-5">
            <HowItWorksStep index={1} icon={Upload} label="Input" description="Paste clinical text or ask a question." />
            <HowItWorksStep index={2} icon={ScanSearch} label="Extract" description="AI extracts key clinical entities." />
            <HowItWorksStep
              index={3}
              icon={Sparkles}
              label="Summarize"
              description="AI generates a concise, structured summary."
            />
            <HowItWorksStep
              index={4}
              icon={MessageSquare}
              label="Assist"
              description="Get cited answers and guidance."
              isLast
            />
          </Card>
        </div>
      </section>

      {/* Clinical activity snapshot (real data only — see component docstring) */}
      <section>
        <DashboardSnapshot />
      </section>

      {/* System status (real, live-checked) */}
      <section>
        <SystemStatusPanel />
      </section>

      {/* Trust trio */}
      <section className="grid grid-cols-1 gap-4 border-t border-border pt-10 sm:grid-cols-3">
        {TRUST_ITEMS.map((item) => (
          <div key={item.title} className="flex flex-col items-center text-center">
            <IconBadge icon={item.icon} tone="blue" />
            <h3 className="mt-3 text-sm font-semibold text-navy">{item.title}</h3>
            <p className="mt-1 text-sm text-muted-text">{item.description}</p>
          </div>
        ))}
      </section>

      <div className="gms-card p-4 text-xs text-muted-text">
        Clinical Decision Support — evidence and generated content must be reviewed by
        the treating clinician.
      </div>
    </div>
  );
}
