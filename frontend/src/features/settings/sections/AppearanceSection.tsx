import { Check, Monitor, Moon, RotateCcw, Sun } from "lucide-react";
import { useBranding } from "@/api/hooks";
import { useAppearance } from "@/app/appearance";
import { Badge, Button, Card, Field, Input, Segmented, SwitchRow } from "@/components/ui";
import { ACCENT_PRESETS } from "@/lib/color";
import { cn } from "@/lib/utils";
import { SettingsCard } from "../parts";

function ThemeCard({ mode, label, icon: Icon, active, onClick }: { mode: "light" | "dark" | "system"; label: string; icon: typeof Sun; active: boolean; onClick: () => void }) {
  const pane = (dark: boolean) => (
    <div className={cn("flex h-full flex-1 gap-1.5 p-2", dark ? "bg-slate-900" : "bg-slate-50")}>
      <div className={cn("w-5 rounded", dark ? "bg-slate-800" : "bg-white ring-1 ring-slate-200")} />
      <div className="flex flex-1 flex-col gap-1.5">
        <div className={cn("h-2 w-3/4 rounded", dark ? "bg-slate-700" : "bg-slate-200")} />
        <div className={cn("flex-1 rounded", dark ? "bg-slate-800" : "bg-white ring-1 ring-slate-200")}><div className="m-1.5 h-1.5 w-1/2 rounded bg-primary" /></div>
      </div>
    </div>
  );
  return (
    <button onClick={onClick} className={cn("overflow-hidden rounded-xl border text-left transition-all hover:border-primary/50", active && "border-primary ring-2 ring-primary/20")}>
      <div className="flex h-20">{mode === "system" ? <>{pane(false)}{pane(true)}</> : pane(mode === "dark")}</div>
      <div className="flex items-center gap-2 border-t px-3 py-2 text-sm font-medium"><Icon className="size-4 text-muted-foreground" /> {label}{active && <Check className="ml-auto size-4 text-primary" />}</div>
    </button>
  );
}

export function AppearanceSection() {
  const { appearance: a, update, reset, effectiveAccent } = useAppearance();
  const { data: branding } = useBranding();
  return (
    <div className="grid gap-[var(--gap)] 2xl:grid-cols-[1fr_340px]">
      <SettingsCard title="Appearance" description="Personal to your account and synced across devices. Changes apply instantly." footer={<Button size="sm" variant="ghost" onClick={reset}><RotateCcw /> Reset to organisation defaults</Button>}>
        <Field label="Theme">
          <div className="grid grid-cols-3 gap-3">
            <ThemeCard mode="light" label="Light" icon={Sun} active={a.theme === "light"} onClick={() => update({ theme: "light" })} />
            <ThemeCard mode="dark" label="Dark" icon={Moon} active={a.theme === "dark"} onClick={() => update({ theme: "dark" })} />
            <ThemeCard mode="system" label="System" icon={Monitor} active={a.theme === "system"} onClick={() => update({ theme: "system" })} />
          </div>
        </Field>
        <Field label="Accent colour" hint={a.accent ? undefined : `Using the organisation default (${branding?.default_accent ?? "#246BFD"})`}>
          <div className="flex flex-wrap items-center gap-2">
            {ACCENT_PRESETS.map((p) => (
              <button key={p.hex} onClick={() => update({ accent: p.hex })} title={p.name} aria-label={p.name}
                className={cn("flex size-8 items-center justify-center rounded-full ring-offset-2 ring-offset-card transition-transform hover:scale-110", effectiveAccent.toLowerCase() === p.hex.toLowerCase() && "ring-2 ring-foreground/60")} style={{ background: p.hex }}>
                {effectiveAccent.toLowerCase() === p.hex.toLowerCase() && <Check className="size-4 text-white" />}
              </button>
            ))}
            <label className="relative flex size-8 cursor-pointer items-center justify-center overflow-hidden rounded-full border-2 border-dashed border-input" title="Custom colour">
              <span className="text-xs text-muted-foreground">+</span>
              <input type="color" value={effectiveAccent} onChange={(e) => update({ accent: e.target.value })} className="absolute inset-0 cursor-pointer opacity-0" />
            </label>
            <Input value={a.accent ?? ""} onChange={(e) => /^#[0-9a-f]{6}$/i.test(e.target.value) && update({ accent: e.target.value })} placeholder={effectiveAccent} className="w-28 font-mono text-xs" />
            {a.accent && <Button size="xs" variant="ghost" onClick={() => update({ accent: null })}>Use default</Button>}
          </div>
        </Field>
        <div className="grid gap-5 md:grid-cols-2">
          <Field label="Density"><Segmented value={a.density} onChange={(v) => update({ density: v })} options={[{ value: "comfortable", label: "Comfortable" }, { value: "compact", label: "Compact" }]} /></Field>
          <Field label="Corner style"><Segmented value={a.radius} onChange={(v) => update({ radius: v })} options={[{ value: "sharp", label: "Sharp" }, { value: "default", label: "Default" }, { value: "round", label: "Round" }]} /></Field>
          <Field label="Text size"><Segmented value={a.font_scale} onChange={(v) => update({ font_scale: v })} options={[{ value: "sm", label: "Small" }, { value: "md", label: "Default" }, { value: "lg", label: "Large" }]} /></Field>
          <Field label="Typeface"><Segmented value={a.font_family} onChange={(v) => update({ font_family: v })} options={[{ value: "inter", label: "Inter" }, { value: "system", label: "System" }]} /></Field>
        </div>
        <div className="space-y-3 border-t pt-4">
          <SwitchRow label="High contrast" description="Stronger borders and darker secondary text." checked={a.contrast === "high"} onCheckedChange={(v) => update({ contrast: v ? "high" : "normal" })} />
          <SwitchRow label="Reduce motion" description="Turns off animations and transitions." checked={a.reduce_motion} onCheckedChange={(v) => update({ reduce_motion: v })} />
        </div>
      </SettingsCard>
      <Card className="card-pad h-fit space-y-4">
        <div className="text-label">Live preview</div>
        <div className="space-y-3 rounded-xl border bg-background p-4">
          <div className="flex items-center gap-2"><span className="font-semibold">James Carter</span><Badge tone="danger">Penicillin</Badge></div>
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-lg border bg-card p-2.5"><div className="text-xs text-muted-foreground">HbA1c</div><div className="font-semibold num">8.4 %</div><Badge tone="danger" className="mt-1">High</Badge></div>
            <div className="rounded-lg border bg-card p-2.5"><div className="text-xs text-muted-foreground">eGFR</div><div className="font-semibold num">44</div><Badge tone="warning" className="mt-1">Low</Badge></div>
          </div>
          <p className="text-sm">Kidney function has declined <span className="rounded bg-info-soft px-1 font-mono text-[0.68rem] font-semibold text-info-foreground">P1</span> and HbA1c is above target <span className="rounded bg-primary-soft px-1 font-mono text-[0.68rem] font-semibold text-primary-soft-foreground">K2</span>.</p>
          <div className="flex gap-2"><Button size="sm">Primary</Button><Button size="sm" variant="secondary">Secondary</Button><Button size="sm" variant="soft">Soft</Button></div>
        </div>
      </Card>
    </div>
  );
}
