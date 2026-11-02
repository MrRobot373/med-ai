import { ListPlus, X } from "lucide-react";
import { useState } from "react";
import { useMe, useOrders } from "@/api/hooks";
import { Button, Card, CardHeader, Segmented, Skeleton } from "@/components/ui";
import { OrderForm, OrderList } from "@/features/consult/OrdersPanel";
import { canChart } from "@/lib/roles";
import { useWorkspace } from "./context";

type Filter = "open" | "all";

export default function OrdersTab() {
  const { patient } = useWorkspace();
  const { data: me } = useMe();
  const { data, isLoading } = useOrders(patient.id);
  const [filter, setFilter] = useState<Filter>("open");
  const [adding, setAdding] = useState(false);
  const writer = canChart(me?.role);
  const all = data ?? [];
  const rows = filter === "open" ? all.filter((o) => o.status === "ordered" || o.status === "result_received") : all.filter((o) => o.status !== "cancelled");
  const back = all.filter((o) => o.status === "result_received").length;
  return (
    <Card>
      <CardHeader title="Investigations & results" description={back ? `${back} result${back > 1 ? "s" : ""} back and waiting for your review` : "Lab tests, scans and ECGs you ordered, with the returned reports"}
        actions={<>
          <Segmented<Filter> value={filter} onChange={setFilter} options={[{ value: "open", label: "Open" }, { value: "all", label: "All" }]} />
          {writer && <Button size="sm" variant={adding ? "ghost" : "strong"} className="rounded-full" onClick={() => setAdding((a) => !a)}>{adding ? <><X /> Close</> : <><ListPlus /> Order</>}</Button>}
        </>} />
      <div className="card-pad space-y-3">
        {adding && <div className="rounded-xl border bg-subtle/60 p-3"><OrderForm patientId={patient.id} onDone={() => setAdding(false)} /></div>}
        {isLoading ? <Skeleton className="h-40" /> : <OrderList orders={rows} canWrite={writer} canAI={writer} empty={filter === "open" ? "Nothing pending" : "No investigations ordered"} />}
      </div>
    </Card>
  );
}
