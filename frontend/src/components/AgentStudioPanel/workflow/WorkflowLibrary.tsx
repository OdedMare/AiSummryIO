import { ChevronDown, Play, Trash2 } from "lucide-react";
import type { WorkflowVersion } from "@/types";
import { NewItemButton } from "../StudioCommon";
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
      <header><h3>תהליכי עבודה</h3>
        <div className="studio-list-actions">
          <span>{workflows.length} תהליכים</span>
          <NewItemButton label="תהליך חדש" onClick={editor.startNew} />
        </div>
      </header>
      {workflows.map((item) =>
        <WorkflowCard key={item.id} item={item} editor={editor} />)}
      {editor.libraryError
        && <p className="form-error" role="alert">{editor.libraryError}</p>}
	      <label className="dry-run-field"><span>מזהה / MULTIPOLYGON לבדיקה חיה</span>
	        <input dir="ltr" value={editor.dryRunId}
	          placeholder="001234567 או MULTIPOLYGON (...)"
          onChange={(event) => editor.setDryRunId(event.target.value)} />
        <small className="field-hint">
	          הערך יישלח לטולים כמחרוזת אחת ללא שינוי.
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
    <article
      className={`workflow-card${item.agent_enabled ? "" : " is-off"}`}>
      <button type="button" className="workflow-card-main"
        onClick={() => editor.edit(item)}>
        <span className={`status-dot ${item.agent_enabled ? "on" : "off"}`} />
        <span><strong>{item.name}</strong>
          <small>
            {item.role} · {item.agent_enabled ? "פעיל לסוכן" : "כבוי"}
            {" · "}{item.steps.length} שלבים
          </small>
        </span>
        <ChevronDown size={16} />
      </button>
      <div className="workflow-card-actions">
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
