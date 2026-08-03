"use client";

import { FormEvent, useState } from "react";
import {
  CheckCircle2, ChevronDown, Play, Plus, Save, Send, Sparkles,
  Trash2, Wand2, Workflow,
} from "lucide-react";
import { api } from "@/services/api";
import type {
  PackageVersion, WorkflowPlan, WorkflowStep, WorkflowVersion,
} from "@/types";
import { emptyWorkflow, parseJson } from "./forms";
import {
  FieldAgentPopover, PlanChat, PlanChatDrawer, usePlanChat,
} from "./PlanChat";
import WorkflowCanvas, { mappedStep, orderedSteps } from "./WorkflowCanvas";

export default function WorkflowEditor({
  packages, workflows, onRefresh,
}: {
  packages: PackageVersion[];
  workflows: WorkflowVersion[];
  onRefresh: () => Promise<void>;
}) {
  const editor = useWorkflowEditor(packages, onRefresh);
  return (
    <div className="workflow-studio">
      <WorkflowLibrary workflows={workflows} editor={editor} />
      <WorkflowForm packages={packages} editor={editor} />
    </div>
  );
}

function useWorkflowEditor(
  packages: PackageVersion[], onRefresh: () => Promise<void>
) {
  const [form, setForm] = useState(emptyWorkflow);
  const [steps, setSteps] = useState<WorkflowStep[]>([]);
  const [error, setError] = useState("");
  // Publishing and dry runs are triggered from the library column, so their
  // failures are reported there. Routing them to `error` put the reason in the
  // form column, far from the button that caused it, where it went unread.
  const [libraryError, setLibraryError] = useState("");
  const [message, setMessage] = useState("");
  const [dryRunId, setDryRunId] = useState("");
  const [dryResult, setDryResult] = useState("");
  const [saving, setSaving] = useState(false);
  // The canvas and the step cards are two views of one selection: clicking a
  // node scrolls its card into view and highlights both.
  const [selectedKey, setSelectedKey] = useState("");

  const update = (key: keyof typeof emptyWorkflow, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));
  const edit = (item: WorkflowVersion) => {
    setForm(workflowForm(item));
    setSteps(item.steps.map((step) => ({ ...step }))); setDryResult("");
  };
  const addStep = () => setSteps((current) => {
    const step = newStep(current, packages);
    setSelectedKey(step.key);
    return [...current, step];
  });
  const updateStep = (index: number, patch: Partial<WorkflowStep>) =>
    setSteps((current) => current.map((step, position) =>
      position === index ? patchedStep(step, patch) : step));
  const removeStep = (index: number) =>
    setSteps((current) => releaseDependents(
      current.filter((_, position) => position !== index),
      current[index]?.key ?? "",
    ));

  /**
   * Delete by key, for the canvas — where a node is identified by its key
   * rather than by its position in the array.
   *
   * Routed through the same `releaseDependents` as the step card's delete
   * button, so a step feeding another cannot be removed without returning
   * its dependents to the main identifier.
   */
  const removeStepByKey = (key: string) => {
    setSteps((current) => current.some((step) => step.key === key)
      ? releaseDependents(current.filter((step) => step.key !== key), key)
      : current);
    setSelectedKey((selected) => (selected === key ? "" : selected));
  };

  /**
   * Point one step at a new source; the canvas draws this as an edge.
   *
   * The canvas drags from a specific output field, so it supplies the
   * mapping too. An empty field means the source carries no named value —
   * the workflow-level inputs, or a package with no output contract — and
   * clears any mapping left over from a previous connection.
   */
  const connectStep = (
    targetKey: string, source: string, inputField: string,
  ) =>
    setSteps((current) => current.map((step) =>
      step.key === targetKey
        ? patchedStep(step, { input_source: source, input_field: inputField })
        : step));
  const disconnectStep = (targetKey: string) =>
    connectStep(targetKey, "workflow.id", "");

  const save = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError(""); setMessage("");
    try {
      await api.createWorkflow(workflowPayload(form, steps));
      setMessage("נשמרה טיוטת תהליך חדשה.");
      setForm(emptyWorkflow); setSteps([]); await onRefresh();
    } catch (reason) {
      setError(errorMessage(reason, "השמירה נכשלה"));
    } finally {
      setSaving(false);
    }
  };
  const publish = async (id: string) => {
    setLibraryError("");
    try {
      await api.publishWorkflow(id); await onRefresh();
    } catch (reason) {
      setLibraryError(errorMessage(reason, "הפרסום נכשל"));
    }
  };
  const dryRun = async (id: string) => {
    if (!dryRunId.trim()) return setLibraryError("יש להזין מזהה בדיקה");
    setDryResult("מריץ חבילות…"); setLibraryError("");
    try {
      setDryResult(JSON.stringify(await api.dryRun(id, dryRunId.trim()), null, 2));
    } catch (reason) {
      setDryResult(""); setLibraryError(errorMessage(reason, "הבדיקה נכשלה"));
    }
  };
  /** Load an agent proposal into the form as an editable draft, never saved. */
  const loadPlan = (plan: WorkflowPlan) => {
    if (!plan.can_build) return;
    setForm(planForm(plan)); setSteps(plan.steps.map((step) => ({ ...step })));
    setMessage("הצעת הסוכן נטענה כטיוטה. יש לבדוק אותה לפני השמירה.");
  };

  /**
   * The steps alone, from an interview opened on the route itself.
   *
   * `loadPlan` replaces the whole form because it follows a conversation about
   * the whole workflow. Here the FDE asked only what the route should do, so
   * the name and description they already wrote stay as they are.
   */
  const loadPlanSteps = (plan: WorkflowPlan) => {
    if (!plan.can_build) return;
    setSteps(plan.steps.map((step) => ({ ...step })));
    setSelectedKey("");
    setMessage("שלבי הסוכן נטענו לקנבס. יש לבדוק את החיבורים לפני השמירה.");
  };
  /**
   * A complete one-step workflow wrapping a single tool.
   *
   * The common case is not a pipeline at all: an FDE wants to expose one
   * FLAPI package as a route and see its rows. Building that by hand meant
   * naming the workflow, adding a step, picking the tool, and copying its
   * output contract into `output_schema` by hand. Everything here is already
   * known from the package itself.
   *
   * The step reads `workflow.id` — the only source a first step can have —
   * so the result is immediately valid and, being a single level, runs as
   * one call.
   */
  const createFromTool = (item: PackageVersion) => {
    setForm({
      ...emptyWorkflow,
      name: item.name,
      description: item.description,
      role: "detail",
      // The section contract is shared and added by the backend; a workflow's
      // own schema only extends it. Publishing the tool's output as `fields`
      // is what surfaces the package's JSON on the section it produces.
      output_schema: JSON.stringify(toolOutputSchema(item), null, 2),
      examples: "[]",
    });
    const step: WorkflowStep = {
      key: "step1", name: item.name, package_version_id: item.id,
      depends_on: [], input_source: "workflow.id", input_field: "",
      summary_prompt: "",
    };
    setSteps([step]);
    setSelectedKey(step.key);
    setDryResult("");
    setError("");
    setMessage(
      `נוצרה טיוטת תהליך עם הטול „${item.name}” וחוזה הפלט שלו. ` +
      "בדקו ושמרו.",
    );
  };

  const reset = () => { setForm(emptyWorkflow); setSteps([]); };

  return {
    form, steps, error, message, dryRunId, setDryRunId, dryResult, saving,
    libraryError, selectedKey, setSelectedKey, update, edit, addStep,
    updateStep, removeStep, removeStepByKey, connectStep, disconnectStep,
    save, publish, dryRun, loadPlan, loadPlanSteps, createFromTool, reset,
  };
}

type Editor = ReturnType<typeof useWorkflowEditor>;

function WorkflowLibrary({
  workflows, editor,
}: {
  workflows: WorkflowVersion[];
  editor: Editor;
}) {
  return (
    <section className="workflow-library">
      <header><h3>תהליכי עבודה</h3><span>{workflows.length} תהליכים</span></header>
      {workflows.map((item) =>
        <WorkflowCard key={item.id} item={item} editor={editor} />)}
      {editor.libraryError &&
        <p className="form-error" role="alert">{editor.libraryError}</p>}
      <label className="dry-run-field"><span>מזהה לבדיקה חיה</span>
        <input dir="ltr" value={editor.dryRunId}
          onChange={(e) => editor.setDryRunId(e.target.value)} />
      </label>
    </section>
  );
}

function WorkflowCard({ item, editor }: { item: WorkflowVersion; editor: Editor }) {
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
        {item.status === "draft" &&
          <button type="button" onClick={() => void editor.publish(item.id)}>
            <Send size={15} /> פרסום
          </button>}
        <button type="button" onClick={() => void editor.dryRun(item.id)}>
          <Play size={15} /> בדיקה חיה
        </button>
      </div>
    </article>
  );
}

function WorkflowForm({
  packages, editor,
}: {
  packages: PackageVersion[];
  editor: Editor;
}) {
  return (
    <form className="studio-form workflow-form" onSubmit={editor.save}>
      <header className="studio-form-header">
        <span><Workflow size={19} /></span>
        <div>
          <h3>{editor.form.workflow_key ? "גרסה חדשה לתהליך" : "תהליך חדש"}</h3>
          <p>סדרת שלבים שמרכיבה סעיף אחד בסיכום.</p>
        </div>
        <WorkflowPlanChat editor={editor} />
      </header>
      <WorkflowFields editor={editor} />
      <StepEditor packages={packages} editor={editor} />
      <AdvancedWorkflowFields editor={editor} />
      {editor.error &&
        <p className="form-error" role="alert">{editor.error}</p>}
      {editor.message && <p className="form-success">
        <CheckCircle2 size={16} /> {editor.message}
      </p>}
      {editor.dryResult &&
        <pre className="dry-result" dir="ltr">{editor.dryResult}</pre>}
      <WorkflowActions editor={editor} />
    </form>
  );
}

function WorkflowPlanChat({ editor }: { editor: Editor }) {
  const [open, setOpen] = useState(false);
  const chat = usePlanChat<WorkflowPlan>(
    (messages, draft) => api.planWorkflowChat(messages, draft),
  );
  const plan = chat.draft;
  return (
    <PlanChatDrawer open={open} busy={chat.pending}
      onOpen={() => setOpen(true)} onClose={() => setOpen(false)}
      label="שאלו את הסוכן">
      <PlanChat chat={chat}
        title="תשאול על התהליך"
        hint="ספרו מה אתם רוצים לדעת על המזהה. הסוכן ישאל שאלה אחת בכל פעם, עם המלצה, עד שנגיע להסכמה.">
        {plan && <div className="planner-result" aria-live="polite">
          {plan.rationale && <p>{plan.rationale}</p>}
          {!!plan.steps.length && <ol className="plan-chat-steps">
            {plan.steps.map((step) =>
              <li key={step.key}>
                <b dir="ltr">{step.key}</b> <span>{step.name}</span>
                <small dir="ltr">
                  {step.input_source}
                  {step.input_field ? ` → ${step.input_field}` : ""}
                </small>
              </li>)}
          </ol>}
          {!!plan.missing_tools.length && <section>
            <strong>מה חסר כדי להשלים את הבקשה</strong>
            <ul>{plan.missing_tools.map((item, index) =>
              <li key={`${item.name}-${index}`}><b>{item.name}</b>
                <span>{item.reason}</span>
              </li>)}
            </ul>
          </section>}
          {chat.ready && <button type="button" className="planner-button"
            onClick={() => { editor.loadPlan(plan); setOpen(false); }}>
            <Sparkles size={17} aria-hidden="true" /> טעינה לטופס לבדיקה
          </button>}
        </div>}
      </PlanChat>
    </PlanChatDrawer>
  );
}

function WorkflowFields({ editor }: { editor: Editor }) {
  const { form, update } = editor;
  return (
    <>
      <div className="form-grid two">
        <label><span>שם התהליך *
          <WorkflowFieldAgent field="name" editor={editor} /></span>
          <input value={form.name}
            onChange={(e) => update("name", e.target.value)} /></label>
        <label><span>תפקיד
          <WorkflowFieldAgent field="role" editor={editor} /></span>
          <select value={form.role}
            onChange={(e) => update("role", e.target.value)}>
            <option value="baseline">בסיס — תמיד בריצה הראשונה</option>
            <option value="detail">פירוט — לשאלות המשך</option>
            <option value="both">שניהם</option>
          </select></label>
      </div>
      <label><span>מתי להשתמש בתהליך
        <WorkflowFieldAgent field="description" editor={editor} /></span>
        <textarea value={form.description}
          onChange={(e) => update("description", e.target.value)} rows={2} />
      </label>
    </>
  );
}

/** What each focused workflow interview is about, in the FDE's words. */
const WORKFLOW_FIELD_LABELS: Record<WorkflowFocus, string> = {
  name: "שם התהליך",
  role: "תפקיד",
  description: "מתי להשתמש בתהליך",
  system_prompt: "הנחיית סיכום לתהליך",
  steps: "מה המסלול עושה",
};

/** The focused fields, and what the agent writes back for each. */
type WorkflowFocus =
  "name" | "role" | "description" | "system_prompt" | "steps";

/**
 * The agent for one part of the workflow form.
 *
 * `steps` is the reason this exists on more than the text fields: "what the
 * route does" is a question about the wiring, not about a sentence, so that
 * conversation applies the plan's whole step array — the same thing the
 * drawer's "load into the form" button does, scoped to one question. Every
 * other focus writes its single field and nothing else, so a conversation
 * about the summary instruction cannot quietly re-wire the canvas.
 */
function WorkflowFieldAgent({
  field, editor,
}: {
  field: WorkflowFocus;
  editor: Editor;
}) {
  const [open, setOpen] = useState(false);
  const label = WORKFLOW_FIELD_LABELS[field];
  const chat = usePlanChat<WorkflowPlan>(
    (messages, draft) => api.planWorkflowChat(messages, draft, field),
  );
  const plan = chat.draft;
  // A step plan is only offerable once the shared validation gate accepted it;
  // `can_build` false means it names a tool that is not in the catalog.
  const offerSteps = field === "steps" && !!plan?.steps.length
    && plan.can_build;
  const value = field === "steps" ? "" : (plan?.[field] ?? "");
  return (
    <FieldAgentPopover open={open} field={field} label={label}
      busy={chat.pending}
      onOpen={() => setOpen(true)} onClose={() => setOpen(false)}>
      <PlanChat chat={chat} title={label}
        hint={field === "steps"
          ? "ספרו מה המסלול צריך לענות עליו. הסוכן יציע שלבים מהקטלוג ואת החיבור ביניהם."
          : `שוחחו עם הסוכן על "${label}" בלבד.`}>
        {plan && <div className="planner-result" aria-live="polite">
          {field === "steps" && plan.rationale && <p>{plan.rationale}</p>}
          {offerSteps && <ol className="plan-chat-steps">
            {plan.steps.map((step) =>
              <li key={step.key}>
                <b dir="ltr">{step.key}</b> <span>{step.name}</span>
                <small dir="ltr">
                  {step.input_source}
                  {step.input_field ? ` → ${step.input_field}` : ""}
                </small>
              </li>)}
          </ol>}
          {field === "steps" && !!plan.missing_tools.length && <section>
            <strong>מה חסר כדי להשלים את הבקשה</strong>
            <ul>{plan.missing_tools.map((item, index) =>
              <li key={`${item.name}-${index}`}><b>{item.name}</b>
                <span>{item.reason}</span>
              </li>)}
            </ul>
          </section>}
          {value && <>
            <p className="field-agent-proposal-label">ההצעה לשדה:</p>
            <p className="field-agent-proposal">{value}</p>
          </>}
          {chat.ready && (offerSteps || !!value) &&
            <button type="button" className="planner-button"
              onClick={() => {
                if (field === "steps") editor.loadPlanSteps(plan);
                else editor.update(field, value);
                setOpen(false);
              }}>
              <Sparkles size={16} aria-hidden="true" />
              {field === "steps" ? " טעינת השלבים לקנבס" : " טעינה לשדה"}
            </button>}
        </div>}
      </PlanChat>
    </FieldAgentPopover>
  );
}

/**
 * Build a whole workflow from one tool, in a single choice.
 *
 * Wrapping one package as a route is the most common thing an FDE does, and
 * it required four separate acts before: name the workflow, add a step, pick
 * the tool, then copy the tool's output contract into `output_schema` by
 * hand. All of it is derivable from the package.
 *
 * Replacing existing work is confirmed first — this overwrites the form, not
 * just the steps.
 */
function SingleToolWorkflow({
  packages, editor,
}: {
  packages: PackageVersion[];
  editor: Editor;
}) {
  const [open, setOpen] = useState(false);
  if (!packages.length) return null;
  const choose = (item: PackageVersion) => {
    setOpen(false);
    const occupied = editor.steps.length || editor.form.name.trim();
    if (occupied && !window.confirm(
      `להחליף את הטיוטה הנוכחית בתהליך חד-שלבי עם „${item.name}”?`
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

function StepEditor({
  packages, editor,
}: {
  packages: PackageVersion[];
  editor: Editor;
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
      {!editor.steps.length &&
        <p className="panel-empty">הוסיפו שלב ראשון ובחרו טול מהקטלוג.</p>}
    </section>
  );
}

function StepCard({
  step, index, packages, editor,
}: {
  step: WorkflowStep;
  index: number;
  packages: PackageVersion[];
  editor: Editor;
}) {
  const selected = step.key === editor.selectedKey;
  return (
    <article className={`step-card${selected ? " is-selected" : ""}`}
      onFocusCapture={() => editor.setSelectedKey(step.key)}>
      <span className="step-number">{index + 1}</span>
      <div className="form-grid two">
        <label><span>מפתח שלב</span><input dir="ltr" value={step.key}
          onChange={(e) => editor.updateStep(index, { key: e.target.value })} />
        </label>
        <label><span>שם ברור ל-FDE</span><input value={step.name}
          onChange={(e) => editor.updateStep(index, { name: e.target.value })} />
        </label>
        <label><span>טול</span><select value={step.package_version_id}
          onChange={(e) => editor.updateStep(
            index, { package_version_id: e.target.value }
          )}>
          <option value="">בחירת טול</option>
          {packages.map((item) =>
            <option key={item.id} value={item.id}>
              {item.name} · v{item.version}
            </option>)}
        </select></label>
        <label><span>מקור המזהה</span><select value={step.input_source}
          onChange={(e) => editor.updateStep(
            index, { input_source: e.target.value }
          )}>
          <option value="workflow.id">המזהה הראשי</option>
          <option value="workflow.boundaries">האזור מהמפה (MULTIPOLYGON)</option>
          {editor.steps.slice(0, index).map((prior) =>
            <option key={prior.key} value={`steps.${prior.key}`}>
              פלט: {prior.name}
            </option>)}
        </select></label>
        {mappedStep(step) && <InputFieldPicker step={step} index={index}
          packages={packages} editor={editor} />}
      </div>
      <button type="button" className="icon-danger"
        onClick={() => editor.removeStep(index)}
        aria-label={`מחיקת ${step.name}`}><Trash2 size={17} /></button>
    </article>
  );
}

/**
 * Which field of the source step's output carries the next identifier.
 *
 * A dropdown rather than a text box: a typo here is not caught until publish
 * validation rejects the mapping, long after the FDE has stopped thinking
 * about the shape of that data. A package with neither a schema nor examples
 * has no fields to offer, so it falls back to free text instead of showing an
 * empty list that would leave the step unfinishable.
 */
function InputFieldPicker({
  step, index, packages, editor,
}: {
  step: WorkflowStep;
  index: number;
  packages: PackageVersion[];
  editor: Editor;
}) {
  const fields = sourceOutputFields(step, index, editor.steps, packages);
  const label = <span>שדה מזהה מתוך הפלט</span>;
  const set = (value: string) =>
    editor.updateStep(index, { input_field: value });

  if (!fields.length) {
    return (
      <label>{label}
        <input dir="ltr" value={step.input_field}
          onChange={(event) => set(event.target.value)} />
        <small className="field-hint">
          לטול המקור אין עדיין חוזה פלט או דוגמאות, לכן שם השדה מוקלד ידנית.
        </small>
      </label>
    );
  }
  // An existing mapping is offered even when the source no longer lists it,
  // so editing a saved workflow never silently drops a field the FDE chose.
  const known = !step.input_field || fields.includes(step.input_field);
  return (
    <label>{label}
      <select dir="ltr" value={step.input_field}
        onChange={(event) => set(event.target.value)}>
        <option value="">בחירת שדה</option>
        {fields.map((field) =>
          <option key={field} value={field}>{field}</option>)}
        {!known &&
          <option value={step.input_field}>{step.input_field} (לא בקטלוג)</option>}
      </select>
      {!known && <small className="field-hint">
        השדה אינו מופיע בפלט של טול המקור. יש לוודא שהוא עדיין קיים.
      </small>}
    </label>
  );
}

/** Output field names of the package feeding this step, or none. */
function sourceOutputFields(
  step: WorkflowStep, index: number, steps: WorkflowStep[],
  packages: PackageVersion[],
) {
  const sourceKey = step.input_source.startsWith("steps.")
    ? step.input_source.split(".")[1] : "";
  if (!sourceKey) return [];
  const source = steps.slice(0, index).find((prior) => prior.key === sourceKey);
  const item = packages.find(
    (candidate) => candidate.id === source?.package_version_id);
  return item ? outputFields(item) : [];
}

/**
 * Mirrors the backend's `_output_fields`: schema properties unioned with the
 * keys actually seen in the examples, so the picker and the planning agent
 * agree on what a tool emits.
 */
function outputFields(item: PackageVersion) {
  const schema = item.output_schema as { properties?: Record<string, unknown> };
  const properties = schema?.properties;
  const names = new Set<string>(
    properties && typeof properties === "object" ? Object.keys(properties) : []);
  for (const row of item.example_output ?? []) {
    if (row && typeof row === "object") {
      Object.keys(row).forEach((field) => names.add(field));
    }
  }
  return [...names].sort();
}

function AdvancedWorkflowFields({ editor }: { editor: Editor }) {
  return (
    <details className="advanced-block">
      <summary><Sparkles size={16} /> הנחיה, חוזה פלט ודוגמאות</summary>
      <label><span>הנחיית סיכום לתהליך
        <small>איך לקרוא את מה שחזר — נקרא על ידי המודל שמנסח את הסעיף</small>
        <WorkflowFieldAgent field="system_prompt" editor={editor} /></span>
        <textarea value={editor.form.system_prompt}
          onChange={(e) => editor.update("system_prompt", e.target.value)}
          rows={5} />
      </label>
      <label><span>חוזה פלט (JSON Schema)</span>
        <textarea dir="ltr" value={editor.form.output_schema}
          onChange={(e) => editor.update("output_schema", e.target.value)}
          rows={5} />
      </label>
      <label><span>דוגמאות משולבות ובדיקות (JSON)</span>
        <textarea dir="ltr" value={editor.form.examples}
          onChange={(e) => editor.update("examples", e.target.value)} rows={6} />
      </label>
    </details>
  );
}

function WorkflowActions({ editor }: { editor: Editor }) {
  return (
    <div className="form-actions">
      {editor.form.workflow_key &&
        <button type="button" className="secondary-button"
          onClick={editor.reset}>ביטול עריכה</button>}
      <button className="primary-button" type="submit"
        disabled={editor.saving || !editor.steps.length}>
        <Save size={17} /> {editor.saving ? "שומר…" : "שמירת טיוטה"}
      </button>
    </div>
  );
}

function workflowForm(item: WorkflowVersion) {
  return {
    workflow_key: item.workflow_key, name: item.name,
    description: item.description, role: item.role,
    system_prompt: item.system_prompt,
    output_schema: JSON.stringify(item.output_schema, null, 2),
    examples: JSON.stringify(item.examples, null, 2),
  };
}

function planForm(plan: WorkflowPlan) {
  return {
    ...emptyWorkflow, name: plan.name, description: plan.description,
    role: plan.role, system_prompt: plan.system_prompt,
  };
}

/**
 * A workflow `output_schema` that re-exposes one tool's own output contract.
 *
 * A workflow's schema **extends** the shared section contract, and the extra
 * properties come back under `section.fields` (`_merge_output_schema` on the
 * backend). So wrapping the package's rows under a `rows` array is what makes
 * the tool's JSON reachable on the section rather than only in raw evidence.
 *
 * The properties are taken from the package's declared schema when it has
 * one, and inferred from an example row otherwise — mirroring how the canvas
 * derives a tool's output fields.
 */
function toolOutputSchema(item: PackageVersion): Record<string, unknown> {
  const declared = item.output_schema as {
    properties?: Record<string, unknown>;
  } | null;
  const properties = declared?.properties
    && typeof declared.properties === "object"
    ? declared.properties
    : inferredProperties(item.example_output ?? []);
  return {
    type: "object",
    properties: {
      rows: {
        type: "array",
        description: `שורות הפלט של ${item.name}`,
        items: Object.keys(properties).length
          ? { type: "object", properties }
          : { type: "object" },
      },
    },
  };
}

/** Property types guessed from the first example row, when no schema exists. */
function inferredProperties(
  examples: Array<Record<string, unknown>>,
): Record<string, unknown> {
  const row = examples.find(
    (candidate) => candidate && typeof candidate === "object");
  if (!row) return {};
  return Object.fromEntries(Object.entries(row).map(
    ([name, value]) => [name, { type: jsonType(value) }]));
}

function jsonType(value: unknown): string {
  if (typeof value === "number") return "number";
  if (typeof value === "boolean") return "boolean";
  if (Array.isArray(value)) return "array";
  if (value && typeof value === "object") return "object";
  return "string";
}

function workflowPayload(form: typeof emptyWorkflow, steps: WorkflowStep[]) {
  return {
    ...form, workflow_key: form.workflow_key || undefined,
    output_schema: parseJson<Record<string, unknown>>(form.output_schema, {}),
    examples: parseJson<Array<Record<string, unknown>>>(form.examples, []),
    // The canvas allows wiring a node backwards into one drawn earlier, but
    // the backend reads a step's source from the steps already seen in the
    // array. Ordering by dependency level here is what makes an arbitrary
    // drag order savable.
    steps: orderedSteps(steps),
  };
}

/**
 * Reset any step that read a now-deleted step back to the main identifier.
 *
 * Without this a removed step leaves its dependents pointing at a key that no
 * longer exists, which the canvas cannot draw and publish validation rejects
 * with a message about a step the FDE can no longer see.
 */
function releaseDependents(steps: WorkflowStep[], removedKey: string) {
  if (!removedKey) return steps;
  return steps.map((step) => step.input_source === `steps.${removedKey}`
    ? patchedStep(step, { input_source: "workflow.id", input_field: "" })
    : step);
}

// A new step reads the main identifier, so steps stay independent and run in
// parallel until an FDE deliberately maps one onto an earlier step's output.
function newStep(steps: WorkflowStep[], packages: PackageVersion[]) {
  const index = steps.length + 1;
  return {
    key: `step-${index}`, name: `שלב ${index}`,
    package_version_id: packages[0]?.id ?? "", depends_on: [],
    input_source: "workflow.id",
    input_field: "", summary_prompt: "",
  };
}

function patchedStep(step: WorkflowStep, patch: Partial<WorkflowStep>) {
  const next = { ...step, ...patch };
  next.depends_on = next.input_source.startsWith("steps.")
    ? [next.input_source.split(".")[1]] : [];
  return next;
}

function errorMessage(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback;
}
