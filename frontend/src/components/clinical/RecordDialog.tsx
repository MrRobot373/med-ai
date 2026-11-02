import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";
import { Button, Dialog, DialogContent, Field, Input, Select, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface FieldDef {
  name: string;
  label: string;
  type?: "text" | "textarea" | "date" | "datetime" | "select" | "number";
  options?: { value: string; label: string }[];
  required?: boolean;
  wide?: boolean;
  placeholder?: string;
  hint?: string;
}

export function RecordDialog({
  open, onOpenChange, title, description, icon, fields, initial, endpoint, method, onSaved, transform,
}: {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; description?: string; icon?: ReactNode; fields: FieldDef[];
  initial?: Record<string, any>; endpoint: string; method: "POST" | "PATCH"; onSaved: () => void; transform?: (v: Record<string, any>) => Record<string, any>;
}) {
  const [values, setValues] = useState<Record<string, any>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (open) {
      const v: Record<string, any> = {};
      for (const f of fields) {
        let x = initial?.[f.name] ?? (f.type === "select" ? f.options?.[0]?.value : "");
        if (f.type === "datetime" && x) {
          const d = new Date(x);
          x = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
        }
        v[f.name] = x ?? "";
      }
      setValues(v);
      setError(null);
    }
  }, [open, initial, fields]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body: Record<string, any> = {};
    for (const f of fields) {
      const v = values[f.name];
      body[f.name] = v === "" ? null : f.type === "datetime" && v ? new Date(v).toISOString() : f.type === "number" && v !== "" ? Number(v) : v;
    }
    try {
      await api(endpoint, { method, body: transform ? transform(body) : body });
      toast.success("Saved");
      onSaved();
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={title} description={description} icon={icon} size="lg" footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button type="submit" form="record-form" loading={busy}>Save</Button></>}>
        <form id="record-form" onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
          {error && <div className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger-foreground sm:col-span-2">{error}</div>}
          {fields.map((f) => (
            <Field key={f.name} label={f.label} required={f.required} hint={f.hint} className={cn(f.wide && "sm:col-span-2")}>
              {f.type === "textarea" ? <Textarea value={values[f.name] ?? ""} onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))} placeholder={f.placeholder} rows={4} />
                : f.type === "select" ? <Select value={values[f.name]} onValueChange={(x) => setValues((v) => ({ ...v, [f.name]: x }))} options={f.options ?? []} />
                : <Input type={f.type === "datetime" ? "datetime-local" : f.type ?? "text"} required={f.required} value={values[f.name] ?? ""} onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))} placeholder={f.placeholder} step={f.type === "number" ? "any" : undefined} />}
            </Field>
          ))}
        </form>
      </DialogContent>
    </Dialog>
  );
}
