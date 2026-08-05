import { ChevronDown, Play, Send, Trash2 } from "lucide-react";
import type { WorkflowVersion } from "@/types";
import type { WorkflowEditorController } from "./useWorkflowEditor";

export default function WorkflowLibrary({
  workflows,
  editor,
}: {
  workflows: WorkflowVersion[];
  editor: WorkflowEditorController;
}) {
  return (
    <section className="workflow-library">
      <header><h3>תהליכי עבודה</h3><span>{workflows.length} תהליכים</span></header>
      {workflows.map((item) =>
        <WorkflowCard key={item.id} item={item} editor={editor} />)}
      {editor.libraryError
        && <p className="form-error" role="alert">{editor.libraryError}</p>}
      <label className="dry-run-field"><span>מזהה לבדיקה חיה</span>
        <input dir="ltr" value={editor.dryRunId} placeholder="001234567"
          onChange={(event) => editor.setDryRunId(event.target.value)} />
        <small className="field-hint">
          המזהה יישלח לטולים בתהליך לצורך בדיקה בלבד.
        </small>
      </label>
    </section>
  );
}

function WorkflowCard({
  item,
  editor,
}: {
  item: WorkflowVersion;
  editor: WorkflowEditorController;
}) {
  return (
    <article className="workflow-card">
      <button type="button" className="workflow-card-main"
        onClick={() => editor.edit(item)}>
        <span className={`status-dot ${item.status}`} />
        <span><strong>{item.name}</strong>
          <small>{item.role} · v{item.version} · {item.steps.length} שלבים</small>
        </span>
        <ChevronDown size={16} />
      </button>
      <div className="workflow-card-actions">
        {item.status === "draft"
          && <button type="button" onClick={() => void editor.publish(item.id)}>
            <Send size={15} /> פרסום
          </button>}
        <button type="button" onClick={() => void editor.dryRun(item.id)}>
          <Play size={15} /> בדיקה חיה
        </button>
        <button type="button" className="danger-action"
          onClick={() => void editor.remove(item)}
          aria-label={`מחיקת התהליך ${item.name}`}>
          <Trash2 size={15} aria-hidden="true" /> מחיקה
        </button>
      </div>
    </article>
  );
}
