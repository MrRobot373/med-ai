import { useState, type ReactNode } from "react";
import { Button, Dialog, DialogContent } from "@/components/ui";

export function ConfirmDialog({
  trigger, title, description, confirmLabel = "Confirm", danger, onConfirm,
}: { trigger: ReactNode; title: ReactNode; description?: ReactNode; confirmLabel?: string; danger?: boolean; onConfirm: () => Promise<unknown> | void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <span onClick={() => setOpen(true)} className="contents">{trigger}</span>
      <DialogContent
        size="sm" title={title} description={description}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant={danger ? "danger" : "primary"} loading={busy} onClick={async () => { setBusy(true); try { await onConfirm(); setOpen(false); } finally { setBusy(false); } }}>
              {confirmLabel}
            </Button>
          </>
        }
      />
    </Dialog>
  );
}
