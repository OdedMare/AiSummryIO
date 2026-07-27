"use client";

import { FormEvent, useState } from "react";
import {
  Bot, CheckCircle2, ChevronDown, GitFork, LoaderCircle, Play, Plus, Save,
  Send, Sparkles, Trash2, Workflow,
} from "lucide-react";
import { api } from "@/services/api";
import type {
  PackageVersion, WorkflowPlan, WorkflowStep, WorkflowVersion,
} from "@/types";
import { emptyWorkflow, parseJson } from "./forms";

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
  const [message, setMessage] = useState("");
  const [dryRunId, setDryRunId] = useState("");
  const [dryResult, setDryResult] = useState("");
  const [saving, setSaving] = useState(false);
  const [planPrompt, setPlanPrompt] = useState("");
  const [planResult, setPlanResult] = useState<WorkflowPlan | null>(null);
  const [planning, setPlanning] = useState(false);

  const update = (key: keyof typeof emptyWorkflow, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));
  const edit = (item: WorkflowVersion) => {
    setForm(workflowForm(item));
    setSteps(item.steps.map((step) => ({ ...step }))); setDryResult("");
  };
  const addStep = () => setSteps((current) => [
    ...current, newStep(current, packages)
  ]);
  const updateStep = (index: number, patch: Partial<WorkflowStep>) =>
    setSteps((current) => current.map((step, position) =>
      position === index ? patchedStep(step, patch) : step));
  const removeStep = (index: number) =>
    setSteps((current) => current.filter((_, position) => position !== index));

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
    setError("");
    try {
      await api.publishWorkflow(id); await onRefresh();
    } catch (reason) {
      setError(errorMessage(reason, "הפרסום נכשל"));
    }
  };
  const dryRun = async (id: string) => {
    if (!dryRunId.trim()) return setError("יש להזין מזהה בדיקה");
    setDryResult("מריץ חבילות…"); setError("");
    try {
      setDryResult(JSON.stringify(await api.dryRun(id, dryRunId.trim()), null, 2));
    } catch (reason) {
      setDryResult(""); setError(errorMessage(reason, "הבדיקה נכשלה"));
    }
  };
  const planWorkflow = async () => {
    if (!planPrompt.trim()) return setError("יש לתאר מה התהליך צריך להשיג");
    setPlanning(true); setError(""); setMessage("");
    try {
      const result = await api.planWorkflow(planPrompt.trim());
      setPlanResult(result);
      if (result.can_build) {
        setForm(planForm(result)); setSteps(result.steps);
        setMessage("הצעת הסוכן נטענה כטיוטה. יש לבדוק אותה לפני השמירה.");
      }
    } catch (reason) {
      setError(errorMessage(reason, "תכנון התהליך נכשל"));
    } finally {
      setPlanning(false);
    }
  };
  const reset = () => { setForm(emptyWorkflow); setSteps([]); };

  return {
    form, steps, error, message, dryRunId, setDryRunId, dryResult, saving,
    planPrompt, setPlanPrompt, planResult, planning, update, edit, addStep,
    updateStep, removeStep, save, publish, dryRun, planWorkflow, reset,
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
      <WorkflowPlanner editor={editor} />
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

function WorkflowPlanner({ editor }: { editor: Editor }) {
  return (
    <section className="workflow-planner" aria-labelledby="workflow-planner-title">
      <header><span><Bot size={19} /></span><div>
        <h3 id="workflow-planner-title">בניית workflow בעזרת הסוכן</h3>
        <p>הצעת AI בלבד: הסוכן משתמש בטולים הקיימים או מפרט מה חסר.</p>
      </div></header>
      <label><span>הנחיית FDE</span><textarea value={editor.planPrompt}
        onChange={(e) => editor.setPlanPrompt(e.target.value)} rows={4}
        placeholder="לדוגמה: בנה תהליך שמאתר בעלות, קשרים וסיכונים סביב המזהה" />
      </label>
      <button type="button" className="planner-button"
        onClick={() => void editor.planWorkflow()}
        disabled={editor.planning || !editor.planPrompt.trim()}>
        {editor.planning ? <LoaderCircle className="spin" size={17} /> :
          <Sparkles size={17} />}
        {editor.planning ? "מתכנן…" : "הרכבת הצעה"}
      </button>
      {editor.planResult && <PlanResult plan={editor.planResult} />}
    </section>
  );
}

function PlanResult({ plan }: { plan: WorkflowPlan }) {
  return (
    <div className="planner-result" aria-live="polite">
      {plan.rationale && <p>{plan.rationale}</p>}
      {!!plan.missing_tools.length && <section>
        <strong>מה חסר כדי להשלים את הבקשה</strong>
        <ul>{plan.missing_tools.map((item, index) =>
          <li key={`${item.name}-${index}`}><b>{item.name}</b>
            <span>{item.reason}</span>
            {(item.input_description || item.output_description) &&
              <small>קלט: {item.input_description || "לא צוין"} · פלט:{" "}
                {item.output_description || "לא צוין"}
              </small>}
          </li>)}
        </ul>
      </section>}
    </div>
  );
}

function WorkflowFields({ editor }: { editor: Editor }) {
  const { form, update } = editor;
  return (
    <>
      <header><span><Workflow size={19} /></span><div>
        <h3>{form.workflow_key ? "גרסת תהליך חדשה" : "תהליך חדש"}</h3>
        <p>כל שלב משתמש בגרסת טול קבועה ובפלט שכבר קיים.</p>
      </div></header>
      <div className="form-grid two">
        <label><span>שם התהליך *</span><input value={form.name}
          onChange={(e) => update("name", e.target.value)} /></label>
        <label><span>תפקיד</span><select value={form.role}
          onChange={(e) => update("role", e.target.value)}>
          <option value="baseline">בסיס — תמיד בריצה הראשונה</option>
          <option value="detail">פירוט — לשאלות המשך</option>
          <option value="both">שניהם</option>
        </select></label>
      </div>
      <label><span>מתי להשתמש בתהליך</span><textarea value={form.description}
        onChange={(e) => update("description", e.target.value)} rows={2} />
      </label>
    </>
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
      <header><div><h4>שלבי התהליך</h4>
        <p>מיפוי הקלט מגדיר את חיבורי התלות.</p>
      </div><button type="button" className="secondary-button"
        onClick={editor.addStep} disabled={!packages.length}>
        <Plus size={16} /> הוספת שלב
      </button></header>
      {editor.steps.map((step, index) =>
        <StepCard key={`${step.key}-${index}`} step={step} index={index}
          packages={packages} editor={editor} />)}
      {!editor.steps.length &&
        <p className="panel-empty">הוסיפו שלב ראשון ובחרו טול מהקטלוג.</p>}
      {!!editor.steps.length && <GraphPreview steps={editor.steps} />}
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
  return (
    <article className="step-card">
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
        {mappedStep(step) && <label><span>שדה מזהה מתוך הפלט</span>
          <input dir="ltr" value={step.input_field}
            onChange={(e) => editor.updateStep(
              index, { input_field: e.target.value }
            )} />
        </label>}
      </div>
      <button type="button" className="icon-danger"
        onClick={() => editor.removeStep(index)}
        aria-label={`מחיקת ${step.name}`}><Trash2 size={17} /></button>
    </article>
  );
}

function GraphPreview({ steps }: { steps: WorkflowStep[] }) {
  const levels = stepLevels(steps);
  return (
    <div className="graph-preview" aria-label="תצוגה מקדימה של התהליך">
      {levels.map((level, index) =>
        <div className="graph-level" key={index}>
          <span className="graph-level-label">
            {level.length > 1 ? `שלב ${index + 1} · ${level.length} במקביל`
              : `שלב ${index + 1}`}
          </span>
          <div className="graph-level-steps">
            {level.map((step) => <b key={step.key}>{step.name}</b>)}
          </div>
          {index < levels.length - 1 && <GitFork size={15} />}
        </div>)}
    </div>
  );
}

// Mirrors the backend's step_levels: steps whose dependencies are all
// satisfied by earlier levels share a level and run concurrently.
function stepLevels(steps: WorkflowStep[]) {
  const levels: WorkflowStep[][] = [];
  const placed = new Set<string>();
  let remaining = [...steps];
  while (remaining.length) {
    const level = remaining.filter((step) =>
      dependencies(step).every((key) => placed.has(key)));
    if (!level.length) {
      levels.push(remaining);
      break;
    }
    level.forEach((step) => placed.add(step.key));
    levels.push(level);
    remaining = remaining.filter((step) => !level.includes(step));
  }
  return levels;
}

function dependencies(step: WorkflowStep) {
  const declared = new Set(step.depends_on ?? []);
  const parts = (step.input_source || "workflow.id").split(".");
  if (parts.length >= 2 && parts[0] === "steps") declared.add(parts[1]);
  return [...declared];
}

function AdvancedWorkflowFields({ editor }: { editor: Editor }) {
  return (
    <details className="advanced-block">
      <summary><Sparkles size={16} /> הנחיה, חוזה פלט ודוגמאות</summary>
      <label><span>הנחיית סיכום לתהליך</span>
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

function workflowPayload(form: typeof emptyWorkflow, steps: WorkflowStep[]) {
  return {
    ...form, workflow_key: form.workflow_key || undefined,
    output_schema: parseJson<Record<string, unknown>>(form.output_schema, {}),
    examples: parseJson<Array<Record<string, unknown>>>(form.examples, []),
    steps,
  };
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

function mappedStep(step: WorkflowStep) {
  return step.input_source !== "workflow.id" &&
    step.input_source !== "workflow.boundaries";
}

function errorMessage(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback;
}
