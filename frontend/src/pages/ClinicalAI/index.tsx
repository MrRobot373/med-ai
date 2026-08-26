import { ClinicalAIWorkspace } from "./Workspace";
import { GENERAL_SUGGESTED_QUESTIONS } from "./scope";

/** Global Clinical AI entry point — general conversations and local-knowledge-only
 * lookups that aren't tied to a specific patient. Patient-scoped conversations live
 * on that patient's own Clinical AI tab (see pages/PatientWorkspace/ClinicalAI.tsx),
 * where "current patient" / "this encounter" / "this report" scopes actually make
 * sense to offer. */
export default function ClinicalAIPage() {
  return (
    <div className="w-full">
      <ClinicalAIWorkspace
        implementedScopes={["general", "local_knowledge_only"]}
        suggestedQuestionsFor={() => GENERAL_SUGGESTED_QUESTIONS}
        heightClass="h-[calc(100vh-6.5rem)]"
      />
    </div>
  );
}
