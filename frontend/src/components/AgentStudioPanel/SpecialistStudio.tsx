"use client";

import { FormEvent, useState } from "react";
import {
  Bot, BookOpen, Check, LoaderCircle, Save, Send, Workflow,
} from "lucide-react";
import { api } from "@/services/api";
import type { AgentContent, WorkflowVersion } from "@/types";

interface SpecialistForm {
  content_key: string;
  name: string;
  description: string;
  content: string;
  workflow_keys: string[];
  skill_keys: string[];
}

const emptySpecialist: SpecialistForm = {
  content_key: "", name: "", description: "", content: "",
  workflow_keys: [], skill_keys: [],
};

export default function SpecialistStudio({
  items, workflows, skills, onRefresh,
}: {
  items: AgentContent[];
  workflows: WorkflowVersion[];
  skills: AgentContent[];
  onRefresh: () => Promise<void>;
}) {
  const [form, setForm] = useState<SpecialistForm>(emptySpecialist);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState("");
  const edit = (item: AgentContent) => setForm({
    content_key: item.content_key,
    name: item.name,
    description: item.description,
    content: item.content,
    workflow_keys: item.config?.workflow_keys ?? [],
    skill_keys: item.config?.skill_keys ?? [],
  });
  const update = (patch: Partial<SpecialistForm>) =>
    setForm((current) => ({ ...current, ...patch }));
  const save = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError("");
    try {
      await api.createContent({
        content_key: form.content_key || undefined,
        kind: "agent",
        name: form.name,
        description: form.description,
        content: form.content,
        config: {
          workflow_keys: form.workflow_keys,
          skill_keys: form.skill_keys,
        },
        user_selectable: false,
      });
      setForm(emptySpecialist);
      await onRefresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "שמירת המומחה נכשלה");
    } finally {
      setSaving(false);
    }
  };
  const publish = async (item: AgentContent) => {
    setPublishing(item.id); setError("");
    try {
      await api.publishContent(item.id);
      await onRefresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "פרסום המומחה נכשל");
    } finally {
      setPublishing("");
    }
  };
  return (
    <div className="studio-split specialist-studio">
      <SpecialistList items={items} onEdit={edit} onPublish={publish}
        publishing={publishing} />
      <SpecialistFormView form={form} update={update} workflows={workflows}
        skills={skills} save={save} saving={saving} error={error}
        reset={() => { setForm(emptySpecialist); setError(""); }} />
    </div>
  );
}

function SpecialistList({
  items, onEdit, onPublish, publishing,
}: {
  items: AgentContent[];
  onEdit: (item: AgentContent) => void;
  onPublish: (item: AgentContent) => Promise<void>;
  publishing: string;
}) {
  return (
    <section className="studio-list">
      <header><h3>מומחים</h3><span>{items.length} מומחים</span></header>
      {!items.length && <p className="panel-empty">
        <Bot size={18} aria-hidden="true" /> עדיין לא הוגדרו מומחים.
      </p>}
      {items.map((item) => <article className="specialist-card" key={item.id}>
        <button type="button" className="specialist-card-main"
          onClick={() => onEdit(item)}>
          <span className="catalog-icon"><Bot size={17} aria-hidden="true" /></span>
          <span><strong>{item.name}</strong><small>
            v{item.version} · {item.config?.workflow_keys.length ?? 0} Workflows
            {item.config?.skill_keys.length
              ? ` · ${item.config.skill_keys.length} Skills` : ""}
          </small></span>
          <span className={`status-dot ${item.status}`} aria-label={
            item.status === "published" ? "מפורסם" : "טיוטה"} />
        </button>
        {item.status === "draft" && <button type="button"
          className="specialist-publish"
          onClick={() => void onPublish(item)} disabled={publishing === item.id}>
          {publishing === item.id
            ? <LoaderCircle className="spin" size={15} aria-hidden="true" />
            : <Send size={15} aria-hidden="true" />}
          {publishing === item.id ? "מפרסם…" : "פרסום"}
        </button>}
      </article>)}
    </section>
  );
}

function SpecialistFormView({
  form, update, workflows, skills, save, saving, error, reset,
}: {
  form: SpecialistForm;
  update: (patch: Partial<SpecialistForm>) => void;
  workflows: WorkflowVersion[];
  skills: AgentContent[];
  save: (event: FormEvent) => Promise<void>;
  saving: boolean;
  error: string;
  reset: () => void;
}) {
  return (
    <form className="studio-form specialist-form" onSubmit={save}>
      <header><span><Bot size={19} aria-hidden="true" /></span><div>
        <h3>{form.content_key ? "גרסה חדשה של המומחה" : "מומחה חדש"}</h3>
        <p>המנהל מאציל משימה; רק המומחה מפעיל את ה־Workflows שהוקצו לו.</p>
      </div></header>
      <div className="form-grid two">
        <label><span>שם המומחה *</span><input value={form.name}
          placeholder="לדוגמה: מומחה Geo"
          onChange={(event) => update({ name: event.target.value })} /></label>
        <label><span>תחום אחריות</span><input value={form.description}
          placeholder="מתי המנהל צריך לבחור במומחה"
          onChange={(event) => update({ description: event.target.value })} /></label>
      </div>
      <label><span>הנחיות המומחה *</span>
        <textarea className="content-editor" rows={10} value={form.content}
          placeholder="הגדר מה לבדוק, איך לנתח, אילו פערים להציף ואיך לדווח למנהל."
          onChange={(event) => update({ content: event.target.value })} />
      </label>
      <CapabilityPicker icon={Workflow} legend="Workflows מורשים *"
        hint="אלו הכלים של המומחה. בזמן ריצה הוא יבחר רק את המעט שנדרש למשימה."
        empty="אין Workflows זמינים. יש ליצור ולפרסם Workflow קודם."
        options={workflows.map((workflow) => ({
          key: workflow.workflow_key,
          name: workflow.name,
          description: workflow.description,
          status: workflow.status,
        }))}
        selected={form.workflow_keys}
        onChange={(workflow_keys) => update({ workflow_keys })} />
      <CapabilityPicker icon={BookOpen} legend="Skills זמינים"
        hint="תוכן ה־Skill נטען רק אם המומחה בוחר בו עבור המשימה הנוכחית."
        empty="אין Skills זמינים. אפשר להוסיף אותם באזור Skills והנחיות."
        options={skills.map((skill) => ({
          key: skill.content_key,
          name: skill.name,
          description: skill.description,
          status: skill.status,
        }))}
        selected={form.skill_keys}
        onChange={(skill_keys) => update({ skill_keys })} />
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="specialist-form-note">
        כל Workflow יכול להיות בבעלות מומחה מפורסם אחד בלבד. הפרסום יבדוק
        שה־Workflows וה־Skills שבחרת קיימים בגרסה מפורסמת.
      </div>
      <div className="form-actions">
        {form.content_key && <button type="button" className="secondary-button"
          onClick={reset}>ביטול</button>}
        <button type="submit" className="primary-button"
          disabled={saving || !form.name.trim() || !form.content.trim()
            || !form.workflow_keys.length}>
          {saving
            ? <LoaderCircle className="spin" size={17} aria-hidden="true" />
            : <Save size={17} aria-hidden="true" />}
          {saving ? "שומר…" : "שמירת טיוטה"}
        </button>
      </div>
    </form>
  );
}

interface CapabilityOption {
  key: string;
  name: string;
  description: string;
  status: "draft" | "published" | "archived";
}

function CapabilityPicker({
  icon: Icon, legend, hint, empty, options, selected, onChange,
}: {
  icon: typeof Workflow;
  legend: string;
  hint: string;
  empty: string;
  options: CapabilityOption[];
  selected: string[];
  onChange: (keys: string[]) => void;
}) {
  const toggle = (key: string) => onChange(selected.includes(key)
    ? selected.filter((item) => item !== key)
    : [...selected, key]);
  return (
    <fieldset className="capability-picker">
      <legend><Icon size={16} aria-hidden="true" /> {legend}</legend>
      <p>{hint}</p>
      {!options.length && <p className="capability-empty">{empty}</p>}
      <div className="capability-options">
        {options.map((option) => {
          const checked = selected.includes(option.key);
          return <label key={option.key} className={checked ? "selected" : ""}>
            <input type="checkbox" checked={checked}
              onChange={() => toggle(option.key)} />
            <span className="capability-check" aria-hidden="true">
              {checked && <Check size={13} />}
            </span>
            <span><strong>{option.name}</strong>
              <small>{option.description || option.key}</small>
              <small>{option.status === "published" ? "מפורסם" : "טיוטה"}
                {" · "}<bdi dir="ltr">{option.key}</bdi></small>
            </span>
          </label>;
        })}
      </div>
    </fieldset>
  );
}
