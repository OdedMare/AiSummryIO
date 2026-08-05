import { useState } from "react";
import { Plus, Trash2, Wand2 } from "lucide-react";
import type { PackageVersion, WorkflowStep } from "@/types";
import WorkflowCanvas from "../WorkflowCanvas";
import { WorkflowFieldAgent } from "./WorkflowAgents";
import type { WorkflowEditorController } from "./useWorkflowEditor";
import { sourceOutputFields } from "./workflowModel";
import { mappedStep } from "./workflowGraph";

export default function WorkflowSteps({
  packages,
  editor,
}: {
  packages: PackageVersion[];
  editor: WorkflowEditorController;
}) {
  return (
    <section className="step-editor">
      <header><div><h4>שלבי התהליך
        <WorkflowFieldAgent field="steps" editor={editor} /></h4>
        <p>גררו חיבור בין שלבים בקנבס, או ערכו כל שלב בטופס שמתחתיו.</p>
      </div><div className="step-editor-actions">
        <SingleToolWorkflow packages={packages} editor={editor} />
        <button type="button" className="secondary-button"
          onClick={editor.addStep} disabled={!packages.length}>
          <Plus size={16} /> הוספת שלב
        </button>
      </div></header>
      {!!editor.steps.length && <WorkflowCanvas
        steps={editor.steps} packages={packages}
        selectedKey={editor.selectedKey}
        onSelectStep={editor.setSelectedKey}
        onConnectStep={editor.connectStep}
        onDisconnectStep={editor.disconnectStep}
        onRemoveStep={editor.removeStepByKey} />}
      {editor.steps.map((step, index) =>
        <StepCard key={`${step.key}-${index}`} step={step} index={index}
          packages={packages} editor={editor} />)}
      {!editor.steps.length
        && <p className="panel-empty">הוסיפו שלב ראשון ובחרו טול מהקטלוג.</p>}
    </section>
  );
}

function SingleToolWorkflow({
  packages,
  editor,
}: {
  packages: PackageVersion[];
  editor: WorkflowEditorController;
}) {
  const [open, setOpen] = useState(false);
  if (!packages.length) return null;
  const choose = (item: PackageVersion) => {
    setOpen(false);
    const occupied = editor.steps.length || editor.form.name.trim();
    if (occupied && !window.confirm(
      `להחליף את הטיוטה הנוכחית בתהליך חד-שלבי עם „${item.name}”?`,
    )) return;
    editor.createFromTool(item);
  };
  return (
    <div className="single-tool-workflow">
      <button type="button" className="secondary-button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}>
        <Wand2 size={16} /> תהליך מטול יחיד
      </button>
      {open && <ul className="single-tool-menu" role="menu"
        aria-label="בחירת טול לתהליך חד-שלבי">
        {packages.map((item) =>
          <li key={item.id}>
            <button type="button" role="menuitem" onClick={() => choose(item)}>
              <strong>{item.name}</strong>
              <small dir="ltr">{item.package_id} · v{item.version}</small>
            </button>
          </li>)}
      </ul>}
    </div>
  );
}

function StepCard({
  step,
  index,
  packages,
  editor,
}: {
  step: WorkflowStep;
  index: number;
  packages: PackageVersion[];
  editor: WorkflowEditorController;
}) {
  const selected = step.key === editor.selectedKey;
  return (
    <article className={`step-card${selected ? " is-selected" : ""}`}
      onFocusCapture={() => editor.setSelectedKey(step.key)}>
      <span className="step-number">{index + 1}</span>
      <div className="form-grid two">
        <label><span>מפתח שלב</span><input dir="ltr" value={step.key}
          placeholder="financial-overview"
          onChange={(event) => editor.updateStep(
            index, { key: event.target.value },
          )} />
          <small className="field-hint">
            מזהה טכני ייחודי לחיבורים; אותיות, מספרים, מקף או קו תחתון.
          </small>
        </label>
        <label><span>שם ברור ל-FDE</span><input value={step.name}
          placeholder="לדוגמה: שליפת נתונים פיננסיים"
          onChange={(event) => editor.updateStep(
            index, { name: event.target.value },
          )} />
          <small className="field-hint">
            שם אנושי שמתאר מה השלב מבצע או מחזיר.
          </small>
        </label>
        <label><span>טול</span><select value={step.package_version_id}
          onChange={(event) => editor.updateStep(
            index, { package_version_id: event.target.value },
          )}>
          <option value="">בחירת טול</option>
          {packages.map((item) =>
            <option key={item.id} value={item.id}>
              {item.name} · v{item.version}
            </option>)}
          </select>
          <small className="field-hint">חבילת FLAPI שתורץ בשלב הזה.</small>
        </label>
        <label><span>מקור הקלט</span><select value={step.input_source}
          onChange={(event) => editor.updateStep(
            index, { input_source: event.target.value },
          )}>
          <option value="workflow.id">המזהה הראשי</option>
          <option value="workflow.boundaries">האזור מהמפה (MULTIPOLYGON)</option>
          <option value="workflow.value">ערך קבוע שנשמר בתהליך</option>
          {editor.steps.slice(0, index).map((prior) =>
            <option key={prior.key} value={`steps.${prior.key}`}>
              פלט: {prior.name}
            </option>)}
        </select>
          <small className="field-hint">
            הערך שיועבר לטול: מזהה, אזור, ערך שמור או פלט של שלב קודם.
          </small>
        </label>
        {step.input_source === "workflow.value"
          && <label><span>ערך הקלט השמור *</span>
            <input dir="ltr" value={step.input_value ?? ""} required
              placeholder="001234567"
              onChange={(event) => editor.updateStep(
                index, { input_value: event.target.value },
              )} />
            <small className="field-hint">
              הערך המדויק שיישלח לטול בכל ריצה ויישמר עם גרסת התהליך.
            </small>
          </label>}
        {mappedStep(step) && <InputFieldPicker step={step} index={index}
          packages={packages} editor={editor} />}
      </div>
      <button type="button" className="icon-danger"
        onClick={() => editor.removeStep(index)}
        aria-label={`מחיקת ${step.name}`}><Trash2 size={17} /></button>
    </article>
  );
}

function InputFieldPicker({
  step,
  index,
  packages,
  editor,
}: {
  step: WorkflowStep;
  index: number;
  packages: PackageVersion[];
  editor: WorkflowEditorController;
}) {
  const fields = sourceOutputFields(step, index, editor.steps, packages);
  const label = <span>שדה מזהה מתוך הפלט</span>;
  const set = (value: string) =>
    editor.updateStep(index, { input_field: value });
  if (!fields.length) {
    return (
      <label>{label}
        <input dir="ltr" value={step.input_field} placeholder="company_id"
          onChange={(event) => set(event.target.value)} />
        <small className="field-hint">
          לטול המקור אין עדיין חוזה פלט או דוגמאות, לכן שם השדה מוקלד ידנית.
        </small>
      </label>
    );
  }
  const known = !step.input_field || fields.includes(step.input_field);
  return (
    <label>{label}
      <select dir="ltr" value={step.input_field}
        onChange={(event) => set(event.target.value)}>
        <option value="">בחירת שדה</option>
        {fields.map((field) =>
          <option key={field} value={field}>{field}</option>)}
        {!known
          && <option value={step.input_field}>
            {step.input_field} (לא בקטלוג)
          </option>}
      </select>
      <small className="field-hint">
        {known
          ? "השדה מפלט השלב הקודם שיועבר כמזהה לשלב הזה."
          : "השדה אינו מופיע בפלט של טול המקור. יש לוודא שהוא עדיין קיים."}
      </small>
    </label>
  );
}
