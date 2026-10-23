import { Activity, Binary, Building2, Cpu, Database, Globe, Lock, Palette, SlidersHorizontal, UserRound, Users, type LucideIcon } from "lucide-react";
import { Navigate, NavLink, useParams } from "react-router";
import { useMe } from "@/api/hooks";
import { PageHeader } from "@/components/ui";
import { cn } from "@/lib/utils";
import { AppearanceSection } from "./sections/AppearanceSection";
import { EmbeddingsSection } from "./sections/EmbeddingsSection";
import { ModelsSection } from "./sections/ModelsSection";
import { BrandingSection, ResearchSection, SecuritySection, SystemSection, UsersSection } from "./sections/OrgSections";
import { ProfileSection } from "./sections/ProfileSection";
import { RetrievalSection, VectorSection } from "./sections/RetrievalSection";

interface Item { id: string; label: string; icon: LucideIcon; admin?: boolean; render: () => JSX.Element; description: string }
const GROUPS: { group: string; items: Item[] }[] = [
  { group: "Personal", items: [
    { id: "profile", label: "Profile", icon: UserRound, render: () => <ProfileSection />, description: "Your details, password and sessions." },
    { id: "appearance", label: "Appearance", icon: Palette, render: () => <AppearanceSection />, description: "Theme, accent colour, density and accessibility." },
  ] },
  { group: "AI & retrieval", items: [
    { id: "models", label: "AI models", icon: Cpu, admin: true, render: () => <ModelsSection />, description: "Language, vision and clinical reasoning models; medicines." },
    { id: "embeddings", label: "Embeddings & reranking", icon: Binary, admin: true, render: () => <EmbeddingsSection />, description: "Semantic search models and the vector index." },
    { id: "retrieval", label: "Retrieval tuning", icon: SlidersHorizontal, admin: true, render: () => <RetrievalSection />, description: "Candidate pools, fusion, context budget and chunking." },
    { id: "vector", label: "Vector store", icon: Database, admin: true, render: () => <VectorSection />, description: "Embedded or server Qdrant." },
    { id: "research", label: "Research sources", icon: Globe, admin: true, render: () => <ResearchSection />, description: "External evidence and de-identification." },
  ] },
  { group: "Organisation", items: [
    { id: "branding", label: "Branding", icon: Building2, admin: true, render: () => <BrandingSection />, description: "Name, logo, colours and disclaimer." },
    { id: "users", label: "Users & roles", icon: Users, admin: true, render: () => <UsersSection />, description: "Accounts and permissions." },
    { id: "security", label: "Security", icon: Lock, admin: true, render: () => <SecuritySection />, description: "Sessions and access policy." },
    { id: "system", label: "System status", icon: Activity, render: () => <SystemSection />, description: "Service health and deployment details." },
  ] },
];

export default function SettingsPage() {
  const { section = "profile" } = useParams();
  const { data: me } = useMe();
  const isAdmin = me?.role === "admin";
  const items = GROUPS.flatMap((g) => g.items);
  const current = items.find((i) => i.id === section);
  if (!current || (current.admin && me && !isAdmin)) return <Navigate to="/settings/profile" replace />;

  return (
    <div>
      <PageHeader title="Settings" description={current.description} />
      <div className="grid gap-[var(--gap)] lg:grid-cols-[230px_1fr]">
        <nav className="glass h-fit space-y-4 rounded-2xl border border-white/70 p-2.5 shadow-card dark:border-white/[0.06] lg:sticky lg:top-[88px]">
          {GROUPS.map((g) => {
            const visible = g.items.filter((i) => !i.admin || isAdmin);
            if (!visible.length) return null;
            return (
              <div key={g.group}>
                <div className="text-label mb-1 px-2.5 !text-[0.65rem]">{g.group}</div>
                {visible.map((i) => (
                  <NavLink key={i.id} to={`/settings/${i.id}`} className={({ isActive }) => cn("flex items-center gap-2.5 rounded-full px-3 py-1.5 text-[0.84rem] font-medium transition-colors", isActive ? "bg-strong text-strong-foreground shadow-card" : "text-muted-foreground hover:bg-muted hover:text-foreground")}>
                    <i.icon className="size-4" /> {i.label}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
        <div className="min-w-0 animate-fade-in" key={current.id}>{current.render()}</div>
      </div>
    </div>
  );
}
