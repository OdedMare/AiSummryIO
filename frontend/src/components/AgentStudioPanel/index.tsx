"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle, ArrowLeft, Beaker, BookOpen, Bot, CheckCircle2,
  ChevronDown, GitFork, KeyRound, LoaderCircle, LogOut, PackagePlus,
  Play, Plus, RefreshCw, Save, Send, Sparkles, Trash2, Workflow, Wrench, X,
} from "lucide-react";
import { api } from "@/services/api";
import type {
  AgentContent, PackageVersion, WorkflowPlan, WorkflowStep, WorkflowVersion,
} from "@/types";

type Tab = "packages" | "workflows" | "content" | "review";

const emptyPackage = {
  package_key: "",
  name: "",
  description: "",
  package_id: "",
  input_cube_name: "",
  input_cube_parameter: "",
  input_mode: "single",
  output_cube_name: "",
  query_name: "",
  agent_enabled: true,
  agent_instructions: "",
  example_input: "[]",
  example_output: "[]",
};

const emptyWorkflow = {
  workflow_key: "",
  name: "",
  description: "",
  role: "detail",
  system_prompt: "",
  output_schema: "{}",
  examples: "[]",
};

const parseJson = <T,>(value: string, fallback: T): T => {
  const parsed = value.trim() ? JSON.parse(value) : fallback;
  return parsed as T;
};

function Login({ onLogin }: { onLogin: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.login(password);
      setPassword("");
      onLogin();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "ההתחברות נכשלה");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="admin-login" onSubmit={submit}>
      <span className="login-icon"><KeyRound size={24} /></span>
      <h3>כניסת FDE</h3>
      <p>עריכת חבילות, תהליכים והנחיות מוגנת בסיסמה.</p>
      <label>
        <span>סיסמה</span>
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          autoFocus
        />
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="primary-button" type="submit" disabled={loading || !password}>
        <Send size={17} /> {loading ? "מתחבר…" : "כניסה לסטודיו"}
      </button>
    </form>
  );
}

function PackageCatalog({
  items,
  onRefresh,
}: {
  items: PackageVersion[];
  onRefresh: () => Promise<void>;
}) {
  const [form, setForm] = useState(emptyPackage);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const update = <Key extends keyof typeof emptyPackage>(
    key: Key,
    value: (typeof emptyPackage)[Key],
  ) =>
    setForm((current) => ({ ...current, [key]: value }));

  const edit = (item: PackageVersion) => setForm({
    package_key: item.package_key,
    name: item.name,
    description: item.description,
    package_id: item.package_id,
    input_cube_name: item.input_cube_name,
    input_cube_parameter: item.input_cube_parameter,
    input_mode: item.input_mode,
    output_cube_name: item.output_cube_name,
    query_name: item.query_name,
    agent_enabled: item.agent_enabled,
    agent_instructions: item.agent_instructions,
    example_input: JSON.stringify(item.example_input, null, 2),
    example_output: JSON.stringify(item.example_output, null, 2),
  });

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await api.createPackage({
        ...form,
        package_key: form.package_key || undefined,
        example_input: parseJson<string[]>(form.example_input, []),
        example_output: parseJson<Array<Record<string, unknown>>>(
          form.example_output, [],
        ),
      });
      setMessage("נשמרה גרסת טול חדשה.");
      setForm(emptyPackage);
      await onRefresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "השמירה נכשלה");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="studio-split">
      <section className="studio-list">
        <header><h3>קטלוג טולים</h3><span>{items.length} טולים</span></header>
        {items.map((item) => (
          <button type="button" className="catalog-card" key={item.id} onClick={() => edit(item)}>
            <span className="catalog-icon"><Wrench size={18} /></span>
            <span>
              <strong>{item.name}</strong>
              <small>
                <bdi dir="ltr">{item.package_id} · v{item.version}</bdi>
                {" · "}
                {item.agent_enabled ? "זמין לסוכן" : "ל-workflow בלבד"}
              </small>
            </span>
            <ArrowLeft size={16} />
          </button>
        ))}
        {!items.length && <p className="panel-empty">הוסיפו את טול ה-FLAPI הראשון.</p>}
      </section>

      <form className="studio-form" onSubmit={save}>
        <header>
          <span><PackagePlus size={19} /></span>
          <div>
            <h3>{form.package_key ? "גרסה חדשה לטול" : "טול חדש"}</h3>
            <p>טול הוא חבילת FLAPI שהסוכן יכול לחבר לתהליך או להריץ להעמקה.</p>
          </div>
        </header>
        <div className="form-grid two">
          <label><span>שם תצוגה *</span><input value={form.name} onChange={(e) => update("name", e.target.value)} /></label>
          <label><span>Package ID *</span><input dir="ltr" value={form.package_id} onChange={(e) => update("package_id", e.target.value)} /></label>
          <label><span>Input cube *</span><input dir="ltr" value={form.input_cube_name} onChange={(e) => update("input_cube_name", e.target.value)} /></label>
          <label><span>Input parameter *</span><input dir="ltr" value={form.input_cube_parameter} onChange={(e) => update("input_cube_parameter", e.target.value)} /></label>
          <label><span>מצב קלט</span>
            <select value={form.input_mode} onChange={(e) => update("input_mode", e.target.value)}>
              <option value="single">מזהה יחיד בכל הרצה</option>
              <option value="many">רשימת מזהים בהרצה אחת</option>
            </select>
          </label>
          <label><span>Output cube *</span><input dir="ltr" value={form.output_cube_name} onChange={(e) => update("output_cube_name", e.target.value)} /></label>
        </div>
        <label><span>מתי הטול שימושי</span><textarea value={form.description} onChange={(e) => update("description", e.target.value)} rows={2} /></label>
        <label><span>איך לסכם את תוצאות הטול</span><textarea value={form.agent_instructions} onChange={(e) => update("agent_instructions", e.target.value)} rows={3} /></label>
        <label className="agent-tool-toggle">
          <input
            type="checkbox"
            checked={form.agent_enabled}
            onChange={(e) => update("agent_enabled", e.target.checked)}
          />
          <span>
            זמין לסוכן כטול עצמאי
            <small>מאפשר לבחור בטול לשאלת העמקה גם בלי workflow מוכן.</small>
          </span>
        </label>
        <label><span>Query name (לא חובה)</span><input dir="ltr" value={form.query_name} onChange={(e) => update("query_name", e.target.value)} /></label>
        <details className="advanced-block">
          <summary><Beaker size={16} /> דוגמאות קלט ופלט</summary>
          <label><span>מזהי דוגמה (JSON)</span><textarea dir="ltr" value={form.example_input} onChange={(e) => update("example_input", e.target.value)} rows={3} /></label>
          <label><span>פלט חבילה לדוגמה (JSON)</span><textarea dir="ltr" value={form.example_output} onChange={(e) => update("example_output", e.target.value)} rows={6} /></label>
        </details>
        {error && <p className="form-error" role="alert">{error}</p>}
        {message && <p className="form-success"><CheckCircle2 size={16} /> {message}</p>}
        <div className="form-actions">
          {form.package_key && (
            <button type="button" className="secondary-button" onClick={() => setForm(emptyPackage)}>ביטול עריכה</button>
          )}
          <button className="primary-button" type="submit" disabled={saving}>
            <Save size={17} /> {saving ? "שומר…" : "שמירת גרסה"}
          </button>
        </div>
      </form>
    </div>
  );
}

function WorkflowEditor({
  packages,
  workflows,
  onRefresh,
}: {
  packages: PackageVersion[];
  workflows: WorkflowVersion[];
  onRefresh: () => Promise<void>;
}) {
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
    setForm({
      workflow_key: item.workflow_key,
      name: item.name,
      description: item.description,
      role: item.role,
      system_prompt: item.system_prompt,
      output_schema: JSON.stringify(item.output_schema, null, 2),
      examples: JSON.stringify(item.examples, null, 2),
    });
    setSteps(item.steps.map((step) => ({ ...step })));
    setDryResult("");
  };

  const addStep = () => {
    const index = steps.length + 1;
    setSteps((current) => [...current, {
      key: `step-${index}`,
      name: `שלב ${index}`,
      package_version_id: packages[0]?.id ?? "",
      depends_on: [],
      input_source: index === 1 ? "workflow.id" : `steps.${current.at(-1)?.key}`,
      input_field: "",
      summary_prompt: "",
    }]);
  };

  const updateStep = (index: number, patch: Partial<WorkflowStep>) => {
    setSteps((current) => current.map((step, position) => {
      if (position !== index) return step;
      const next = { ...step, ...patch };
      next.depends_on = next.input_source.startsWith("steps.")
        ? [next.input_source.split(".")[1]]
        : [];
      return next;
    }));
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await api.createWorkflow({
        ...form,
        workflow_key: form.workflow_key || undefined,
        output_schema: parseJson<Record<string, unknown>>(form.output_schema, {}),
        examples: parseJson<Array<Record<string, unknown>>>(form.examples, []),
        steps,
      });
      setMessage("נשמרה טיוטת תהליך חדשה.");
      setForm(emptyWorkflow);
      setSteps([]);
      await onRefresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "השמירה נכשלה");
    } finally {
      setSaving(false);
    }
  };

  const publish = async (id: string) => {
    setError("");
    try {
      await api.publishWorkflow(id);
      await onRefresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "הפרסום נכשל");
    }
  };

  const dryRun = async (id: string) => {
    if (!dryRunId.trim()) {
      setError("יש להזין מזהה בדיקה");
      return;
    }
    setDryResult("מריץ חבילות…");
    setError("");
    try {
      const result = await api.dryRun(id, dryRunId.trim());
      setDryResult(JSON.stringify(result, null, 2));
    } catch (reason) {
      setDryResult("");
      setError(reason instanceof Error ? reason.message : "הבדיקה נכשלה");
    }
  };

  const planWorkflow = async () => {
    if (!planPrompt.trim()) {
      setError("יש לתאר מה התהליך צריך להשיג");
      return;
    }
    setPlanning(true);
    setError("");
    setMessage("");
    try {
      const result = await api.planWorkflow(planPrompt.trim());
      setPlanResult(result);
      if (result.can_build) {
        setForm({
          ...emptyWorkflow,
          name: result.name,
          description: result.description,
          role: result.role,
          system_prompt: result.system_prompt,
        });
        setSteps(result.steps);
        setMessage("הצעת הסוכן נטענה כטיוטה. יש לבדוק אותה לפני השמירה.");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "תכנון התהליך נכשל");
    } finally {
      setPlanning(false);
    }
  };

  return (
    <div className="workflow-studio">
      <section className="workflow-library">
        <header><h3>תהליכי עבודה</h3><span>{workflows.length} תהליכים</span></header>
        {workflows.map((item) => (
          <article className="workflow-card" key={item.id}>
            <button type="button" className="workflow-card-main" onClick={() => edit(item)}>
              <span className={`status-dot ${item.status}`} />
              <span>
                <strong>{item.name}</strong>
                <small>{item.role} · v{item.version} · {item.steps.length} שלבים</small>
              </span>
              <ChevronDown size={16} />
            </button>
            <div className="workflow-card-actions">
              {item.status === "draft" && (
                <button type="button" onClick={() => void publish(item.id)}>
                  <Send size={15} /> פרסום
                </button>
              )}
              <button type="button" onClick={() => void dryRun(item.id)}>
                <Play size={15} /> בדיקה חיה
              </button>
            </div>
          </article>
        ))}
        <label className="dry-run-field">
          <span>מזהה לבדיקה חיה</span>
          <input dir="ltr" value={dryRunId} onChange={(e) => setDryRunId(e.target.value)} />
        </label>
      </section>

      <form className="studio-form workflow-form" onSubmit={save}>
        <section className="workflow-planner" aria-labelledby="workflow-planner-title">
          <header>
            <span><Bot size={19} /></span>
            <div>
              <h3 id="workflow-planner-title">בניית workflow בעזרת הסוכן</h3>
              <p>הצעת AI בלבד: הסוכן משתמש בטולים הקיימים או מפרט מה חסר.</p>
            </div>
          </header>
          <label>
            <span>הנחיית FDE</span>
            <textarea
              value={planPrompt}
              onChange={(e) => setPlanPrompt(e.target.value)}
              rows={4}
              placeholder="לדוגמה: בנה תהליך שמאתר בעלות, קשרים וסיכונים סביב המזהה"
            />
          </label>
          <button
            type="button"
            className="planner-button"
            onClick={() => void planWorkflow()}
            disabled={planning || !planPrompt.trim()}
          >
            {planning ? <LoaderCircle className="spin" size={17} /> : <Sparkles size={17} />}
            {planning ? "מתכנן…" : "הרכבת הצעה"}
          </button>
          {planResult && (
            <div className="planner-result" aria-live="polite">
              {planResult.rationale && <p>{planResult.rationale}</p>}
              {!!planResult.missing_tools.length && (
                <section>
                  <strong>מה חסר כדי להשלים את הבקשה</strong>
                  <ul>
                    {planResult.missing_tools.map((item, index) => (
                      <li key={`${item.name}-${index}`}>
                        <b>{item.name}</b>
                        <span>{item.reason}</span>
                        {(item.input_description || item.output_description) && (
                          <small>
                            קלט: {item.input_description || "לא צוין"} · פלט: {item.output_description || "לא צוין"}
                          </small>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
          )}
        </section>
        <header>
          <span><Workflow size={19} /></span>
          <div><h3>{form.workflow_key ? "גרסת תהליך חדשה" : "תהליך חדש"}</h3><p>כל שלב משתמש בגרסת טול קבועה ובפלט שכבר קיים.</p></div>
        </header>
        <div className="form-grid two">
          <label><span>שם התהליך *</span><input value={form.name} onChange={(e) => update("name", e.target.value)} /></label>
          <label><span>תפקיד</span>
            <select value={form.role} onChange={(e) => update("role", e.target.value)}>
              <option value="baseline">בסיס — תמיד בריצה הראשונה</option>
              <option value="detail">פירוט — לשאלות המשך</option>
              <option value="both">שניהם</option>
            </select>
          </label>
        </div>
        <label><span>מתי להשתמש בתהליך</span><textarea value={form.description} onChange={(e) => update("description", e.target.value)} rows={2} /></label>

        <section className="step-editor">
          <header>
            <div><h4>שלבי התהליך</h4><p>מיפוי הקלט מגדיר את חיבורי התלות.</p></div>
            <button type="button" className="secondary-button" onClick={addStep} disabled={!packages.length}>
              <Plus size={16} /> הוספת שלב
            </button>
          </header>
          {steps.map((step, index) => (
            <article className="step-card" key={`${step.key}-${index}`}>
              <span className="step-number">{index + 1}</span>
              <div className="form-grid two">
                <label><span>מפתח שלב</span><input dir="ltr" value={step.key} onChange={(e) => updateStep(index, { key: e.target.value })} /></label>
                <label><span>שם ברור ל-FDE</span><input value={step.name} onChange={(e) => updateStep(index, { name: e.target.value })} /></label>
                <label><span>טול</span>
                  <select value={step.package_version_id} onChange={(e) => updateStep(index, { package_version_id: e.target.value })}>
                    <option value="">בחירת טול</option>
                    {packages.map((item) => <option key={item.id} value={item.id}>{item.name} · v{item.version}</option>)}
                  </select>
                </label>
                <label><span>מקור המזהה</span>
                  <select value={step.input_source} onChange={(e) => updateStep(index, { input_source: e.target.value })}>
                    <option value="workflow.id">המזהה הראשי</option>
                    {steps.slice(0, index).map((prior) => (
                      <option key={prior.key} value={`steps.${prior.key}`}>פלט: {prior.name}</option>
                    ))}
                  </select>
                </label>
                {step.input_source !== "workflow.id" && (
                  <label><span>שדה מזהה מתוך הפלט</span><input dir="ltr" value={step.input_field} onChange={(e) => updateStep(index, { input_field: e.target.value })} /></label>
                )}
              </div>
              <button type="button" className="icon-danger" onClick={() => setSteps((current) => current.filter((_, position) => position !== index))} aria-label={`מחיקת ${step.name}`}>
                <Trash2 size={17} />
              </button>
            </article>
          ))}
          {!steps.length && <p className="panel-empty">הוסיפו שלב ראשון ובחרו טול מהקטלוג.</p>}
          {!!steps.length && (
            <div className="graph-preview" aria-label="תצוגה מקדימה של התהליך">
              {steps.map((step, index) => (
                <span key={step.key}>
                  <b>{step.name}</b>
                  {index < steps.length - 1 && <GitFork size={15} />}
                </span>
              ))}
            </div>
          )}
        </section>

        <details className="advanced-block">
          <summary><Sparkles size={16} /> הנחיה, חוזה פלט ודוגמאות</summary>
          <label><span>הנחיית סיכום לתהליך</span><textarea value={form.system_prompt} onChange={(e) => update("system_prompt", e.target.value)} rows={5} /></label>
          <label><span>חוזה פלט (JSON Schema)</span><textarea dir="ltr" value={form.output_schema} onChange={(e) => update("output_schema", e.target.value)} rows={5} /></label>
          <label><span>דוגמאות משולבות ובדיקות (JSON)</span><textarea dir="ltr" value={form.examples} onChange={(e) => update("examples", e.target.value)} rows={6} /></label>
        </details>

        {error && <p className="form-error" role="alert">{error}</p>}
        {message && <p className="form-success"><CheckCircle2 size={16} /> {message}</p>}
        {dryResult && <pre className="dry-result" dir="ltr">{dryResult}</pre>}
        <div className="form-actions">
          {form.workflow_key && <button type="button" className="secondary-button" onClick={() => { setForm(emptyWorkflow); setSteps([]); }}>ביטול עריכה</button>}
          <button className="primary-button" type="submit" disabled={saving || !steps.length}>
            <Save size={17} /> {saving ? "שומר…" : "שמירת טיוטה"}
          </button>
        </div>
      </form>
    </div>
  );
}

function ContentStudio({
  items,
  onRefresh,
}: {
  items: AgentContent[];
  onRefresh: () => Promise<void>;
}) {
  const [form, setForm] = useState({
    content_key: "", kind: "skill", name: "", description: "", content: "",
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const edit = (item: AgentContent) => setForm({
    content_key: item.content_key,
    kind: item.kind,
    name: item.name,
    description: item.description,
    content: item.content,
  });

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.createContent({
        ...form,
        content_key: form.content_key || undefined,
      });
      setForm({ content_key: "", kind: "skill", name: "", description: "", content: "" });
      await onRefresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "השמירה נכשלה");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="studio-split">
      <section className="studio-list">
        <header><h3>מיומנויות והנחיות</h3><span>{items.length} פריטים</span></header>
        {items.map((item) => (
          <article className="content-card" key={item.id}>
            <button type="button" onClick={() => edit(item)}>
              <span>{item.kind === "skill" ? <BookOpen size={17} /> : <Sparkles size={17} />}</span>
              <span><strong>{item.name}</strong><small>{item.kind} · v{item.version} · {item.status}</small></span>
            </button>
            {item.status === "draft" && (
              <button type="button" onClick={() => void api.publishContent(item.id).then(onRefresh)}><Send size={15} /> פרסום</button>
            )}
          </article>
        ))}
      </section>
      <form className="studio-form" onSubmit={save}>
        <header><span><BookOpen size={19} /></span><div><h3>{form.content_key ? "גרסה חדשה" : "תוכן סוכן חדש"}</h3><p>קצר, ממוקד, וברור מתי להשתמש בו.</p></div></header>
        <div className="form-grid two">
          <label><span>סוג</span><select value={form.kind} onChange={(e) => setForm((current) => ({ ...current, kind: e.target.value }))}><option value="skill">מיומנות</option><option value="prompt">הנחיית מערכת</option></select></label>
          <label><span>שם *</span><input value={form.name} onChange={(e) => setForm((current) => ({ ...current, name: e.target.value }))} /></label>
        </div>
        <label><span>תיאור הפעלה</span><input value={form.description} onChange={(e) => setForm((current) => ({ ...current, description: e.target.value }))} /></label>
        <label><span>תוכן</span><textarea className="content-editor" value={form.content} onChange={(e) => setForm((current) => ({ ...current, content: e.target.value }))} rows={18} /></label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="form-actions">
          {form.content_key && <button type="button" className="secondary-button" onClick={() => setForm({ content_key: "", kind: "skill", name: "", description: "", content: "" })}>ביטול</button>}
          <button className="primary-button" type="submit" disabled={saving || !form.name || !form.content}><Save size={17} /> שמירת טיוטה</button>
        </div>
      </form>
    </div>
  );
}

function ReviewQueue({ items }: { items: Array<Record<string, unknown>> }) {
  return (
    <section className="review-queue">
      <header><div><h3>תור שיפור</h3><p>משוב שלילי ושאלות הדורשות טיפול FDE.</p></div><span>{items.length} פריטים</span></header>
      {items.map((item) => (
        <article key={String(item.id)}>
          <span className="review-icon"><AlertTriangle size={18} /></span>
          <div>
            <strong>{String(item.comment || "סיכום דורש שיפור")}</strong>
            <small dir="ltr">run {String(item.run_id)} · {String(item.run_status)}</small>
          </div>
        </article>
      ))}
      {!items.length && <p className="panel-empty"><CheckCircle2 size={18} /> אין פריטים פתוחים.</p>}
    </section>
  );
}

export default function AgentStudioPanel({ onClose }: { onClose: () => void }) {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [tab, setTab] = useState<Tab>("workflows");
  const [packages, setPackages] = useState<PackageVersion[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowVersion[]>([]);
  const [content, setContent] = useState<AgentContent[]>([]);
  const [review, setReview] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setError("");
    try {
      const [nextPackages, nextWorkflows, nextContent, nextReview] = await Promise.all([
        api.packages(), api.workflows(), api.content(), api.reviewQueue(),
      ]);
      setPackages(nextPackages);
      setWorkflows(nextWorkflows);
      setContent(nextContent);
      setReview(nextReview);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "טעינת הסטודיו נכשלה");
    }
  }, []);

  useEffect(() => {
    api.adminSession()
      .then(() => {
        setAuthenticated(true);
        void refresh();
      })
      .catch(() => setAuthenticated(false));
  }, [refresh]);

  const counts = useMemo(() => ({
    packages: packages.length,
    workflows: workflows.length,
    content: content.length,
    review: review.length,
  }), [packages, workflows, content, review]);

  return (
    <div className="modal-backdrop studio-backdrop" role="presentation">
      <section className="modal studio-modal" role="dialog" aria-modal="true" aria-labelledby="studio-title">
        <header className="modal-header studio-header">
          <span className="modal-icon"><Workflow size={20} /></span>
          <div><h2 id="studio-title">Agent Studio</h2><p>טולים, תהליכים, מיומנויות ובקרת איכות.</p></div>
          {authenticated && (
            <button type="button" onClick={() => { void api.logout(); setAuthenticated(false); }} aria-label="יציאה מהסטודיו"><LogOut size={19} /></button>
          )}
          <button type="button" onClick={onClose} aria-label="סגירה"><X /></button>
        </header>

        {authenticated === null && <p className="loading-line"><LoaderCircle className="spin" /> בודק הרשאה…</p>}
        {authenticated === false && <Login onLogin={() => { setAuthenticated(true); void refresh(); }} />}
        {authenticated && (
          <>
            <nav className="studio-tabs" aria-label="אזורי Agent Studio">
              {([
                ["packages", "טולים", Wrench],
                ["workflows", "תהליכים", Workflow],
                ["content", "מיומנויות והנחיות", BookOpen],
                ["review", "תור שיפור", AlertTriangle],
              ] as const).map(([key, label, Icon]) => (
                <button type="button" key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>
                  <Icon size={17} /> {label}<span>{counts[key]}</span>
                </button>
              ))}
              <button type="button" className="refresh-button" onClick={() => void refresh()} aria-label="רענון נתונים"><RefreshCw size={17} /></button>
            </nav>
            {error && <p className="studio-global-error" role="alert">{error}</p>}
            <div className="studio-body">
              {tab === "packages" && <PackageCatalog items={packages} onRefresh={refresh} />}
              {tab === "workflows" && <WorkflowEditor packages={packages} workflows={workflows} onRefresh={refresh} />}
              {tab === "content" && <ContentStudio items={content} onRefresh={refresh} />}
              {tab === "review" && <ReviewQueue items={review} />}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
