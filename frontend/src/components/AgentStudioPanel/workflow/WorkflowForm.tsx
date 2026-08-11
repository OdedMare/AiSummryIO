import { CheckCircle2, Workflow } from "lucide-react";
import type { AgentContent, PackageVersion } from "@/types";
import { WorkflowPlanChat } from "./WorkflowAgents";
import {
  AdvancedWorkflowFields,
  WorkflowActions,
  WorkflowFields,
} from "./WorkflowFields";
import WorkflowSteps from "./WorkflowSteps";
import type { WorkflowEditorController } from "./useWorkflowEditor";

export default function WorkflowForm({
  packages,
  agents,
  editor,
}: {
  packages: PackageVersion[];
  agents: AgentContent[];
  editor: WorkflowEditorController;
}) {
  return (
    <form className="studio-form workflow-form" onSubmit={editor.save}>
      <header className="studio-form-header">
        <span><Workflow size={19} /></span>
        <div>
          <h3>{editor.editingId ? "עריכת תהליך" : "תהליך חדש"}</h3>
          <p>סדרת שלבים שמרכיבה סעיף אחד בסיכום.</p>
        </div>
        <WorkflowPlanChat editor={editor} />
      </header>
      <WorkflowFields editor={editor} agents={agents} />
      <WorkflowSteps packages={packages} editor={editor} />
      <AdvancedWorkflowFields editor={editor} />
      {editor.error
        && <p className="form-error" role="alert">{editor.error}</p>}
      {editor.message && <p className="form-success">
        <CheckCircle2 size={16} /> {editor.message}
      </p>}
      {editor.dryResult
        && <pre className="dry-result" dir="ltr">{editor.dryResult}</pre>}
      <WorkflowActions editor={editor} />
    </form>
  );
}
