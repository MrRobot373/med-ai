import { Link } from "react-router-dom";
import {
  BookOpen,
  Cpu,
  Database,
  FileText,
  HeartHandshake,
  ServerCog,
  ShieldCheck,
  Stethoscope,
  Tags,
} from "lucide-react";
import { CapabilityCard } from "@/components/CapabilityCard";
import { IconBadge } from "@/components/IconBadge";
import doctorAiImage from "@/assets/doctor-ai.png";
import gmsLogo from "@/assets/GMS-LOGO.webp";

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
    to: "/settings?tab=knowledge",
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
            Clinical AI That Works
            <br />
            As Hard As You Do
          </h1>
          <p className="mt-4 max-w-lg text-muted-text">
            A privacy-first, on-premise AI platform that helps clinicians move faster and reason deeper —
            automated report analysis, longitudinal patient tracking, evidence-backed Q&amp;A, and intelligent
            note generation, all without a single byte leaving your facility.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-4">
            <a
              href="#capabilities"
              className="inline-flex items-center gap-2 rounded-lg bg-primary-blue px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-blue/90"
            >
              Explore Capabilities
            </a>
          </div>
        </div>
        <div className="mx-auto flex w-full max-w-md items-center justify-center">
          <img
            src={doctorAiImage}
            alt="Doctor AI Assistant"
            className="w-full max-h-[380px] object-contain rounded-2xl drop-shadow-xl"
          />
        </div>
      </section>

      {/* Capabilities (3 columns x 2 rows) */}
      <section id="capabilities">
        <h2 className="mb-4 text-lg font-semibold text-navy">AI Capabilities</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {CAPABILITIES.map((c) => (
            <CapabilityCard key={c.title} {...c} />
          ))}
        </div>
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

      {/* GMS Footer */}
      <footer className="border-t border-border pt-10 pb-6">
        <div className="flex flex-col gap-8 md:flex-row md:items-start md:justify-between">
          <div className="max-w-sm space-y-3">
            <div className="flex items-center gap-3">
              <img src={gmsLogo} alt="GMS Logo" className="h-9 w-9 rounded object-contain" />
              <div>
                {/* <span className="text-base font-bold text-gms-red">GMS</span>{" "} */}
                <span className="text-base font-bold text-navy">MED AI</span>
                <p className="text-xs text-muted-text">Ophthalmology</p>
              </div>
            </div>
            {/* <p className="text-xs leading-relaxed text-muted-text">
              Specialized clinical intelligence platform designed for privacy-first diagnostic support, longitudinal records, and on-premise AI acceleration.
            </p>
            <div className="flex items-center gap-2 text-[11px] text-muted-text">
              <span className="inline-block h-2 w-2 rounded-full bg-success"></span>
              <span>100% On-Premise Local Stack</span>
            </div> */}
          </div>

          <div className="grid grid-cols-2 gap-8 text-xs sm:grid-cols-3">
            <div className="space-y-2.5">
              <div className="font-semibold uppercase tracking-wider text-navy">Platform</div>
              <ul className="space-y-2 text-muted-text">
                <li><Link to="/dashboard" className="transition-colors hover:text-primary-blue">Dashboard</Link></li>
                <li><Link to="/patients" className="transition-colors hover:text-primary-blue">Patients</Link></li>
                <li><Link to="/clinical-ai" className="transition-colors hover:text-primary-blue">Clinical AI</Link></li>
              </ul>
            </div>

            <div className="space-y-2.5">
              <div className="font-semibold uppercase tracking-wider text-navy">Governance</div>
              <ul className="space-y-2 text-muted-text">
                <li><Link to="/settings?tab=privacy" className="transition-colors hover:text-primary-blue">Privacy Policy</Link></li>
                <li><Link to="/settings?tab=knowledge" className="transition-colors hover:text-primary-blue">Guidelines</Link></li>
                <li><Link to="/settings?tab=audit" className="transition-colors hover:text-primary-blue">Audit Trail</Link></li>
              </ul>
            </div>

            <div className="space-y-2.5">
              <div className="font-semibold uppercase tracking-wider text-navy">Support</div>
              <ul className="space-y-2 text-muted-text">
                <li><Link to="/settings?tab=report" className="transition-colors hover:text-primary-blue">Report Issue</Link></li>
                <li><Link to="/settings?tab=system" className="transition-colors hover:text-primary-blue">System Health</Link></li>
                <li><Link to="/settings?tab=account" className="transition-colors hover:text-primary-blue">Account</Link></li>
              </ul>
            </div>
          </div>
        </div>

        <div className="mt-8 flex flex-col items-center justify-between gap-4 border-t border-border pt-6 text-[11px] text-muted-text sm:flex-row">
          <div>
            &copy; {new Date().getFullYear()} GMS. All rights reserved.
          </div>
          {/* <div>
            Clinical Decision Support System &mdash; verification by licensed clinician required.
          </div> */}
        </div>
      </footer>
    </div>
  );
}
