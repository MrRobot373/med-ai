import { MessageSquarePlus } from "lucide-react";
import { useState } from "react";
import { useConversations } from "@/api/hooks";
import { Button, Card } from "@/components/ui";
import { ChatView } from "@/features/assistant/ChatView";
import { ConversationList } from "@/features/assistant/AssistantPage";
import { useWorkspace } from "./context";

export default function AssistantTab() {
  const { patient } = useWorkspace();
  const { data, isLoading } = useConversations(patient.id);
  const [active, setActive] = useState<string | null>(null);
  const [viewKey, setViewKey] = useState("draft-0");
  return (
    <Card className="flex h-[calc(100vh-17rem)] min-h-[560px] overflow-hidden">
      <aside className="hidden w-64 shrink-0 flex-col border-r bg-subtle md:flex">
        <div className="border-b p-3"><Button className="w-full" size="sm" onClick={() => { setActive(null); setViewKey(`draft-${Date.now()}`); }}><MessageSquarePlus /> New conversation</Button></div>
        <div className="flex-1 overflow-y-auto"><ConversationList items={data ?? []} activeId={active} onSelect={(id) => { setActive(id); setViewKey(id); }} loading={isLoading} /></div>
      </aside>
      <ChatView key={viewKey} conversationId={active} patient={{ id: patient.id, full_name: patient.full_name, mrn: patient.mrn }} onCreated={setActive} />
    </Card>
  );
}
