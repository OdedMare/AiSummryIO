"use client";

import { FormEvent, useState } from "react";
import {
  Bot, BookOpen, Check, LoaderCircle, Save, Trash2, Workflow,
} from "lucide-react";
import { api } from "@/services/api";
import type {
  AgentContent, SpecialistPlanDraft, WorkflowVersion,
} from "@/types";
import { SpecialistPlanChat } from "./ContentAgents";
import { NewItemButton } from "./StudioCommon";

interface SpecialistForm {
  content_key: string;
  name: string;
  description: string;
  content: string;
  agent_enabled: boolean;
  workflow_keys: string[];
  skill_keys: string[];
}

const emptySpecialist: SpecialistForm = {
  content_key: "", name: "", description: "", content: "",
  agent_enabled: true, workflow_keys: [], skill_keys: [],
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
  /* Which specialist this form is editing, or "" for a new one. A specialist
     is one row, edited in place: there is no publishing step, so a save takes
     effect immediately and `agent_enabled` is what holds one back. */
  const [editingId, setEditingId] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const edit = (item: AgentContent) => {
    setEditingId(item.id); setError("");
    setForm({
      content_key: item.content_key,
      name: item.name,
      description: item.description,
      content: item.content,
      agent_enabled: item.agent_enabled,
      workflow_keys: item.config?.workflow_keys ?? [],
      skill_keys: item.config?.skill_keys ?? [],
    });
  };
  const reset = () => { setForm(emptySpecialist); setEditingId(""); };
  const startNew = () => { reset(); setError(""); };
  const update = (patch: Partial<SpecialistForm>) =>
    setForm((current) => ({ ...current, ...patch }));

  /**
   * Save the specialist: update the one being edited, or create a new one.
   *
   * Enabling is where the backend checks the configuration holds together —
   * every chosen Workflow and Skill is itself enabled, and no other enabled
   * specialist already owns one of those Workflows. A save that fails that
   * check reports the reason here rather than half-applying.
   */
  const save = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError("");
    try {
      const payload = {
        content_key: form.content_key || undefined,
        kind: "agent",
        name: form.name,
        description: form.description,
        content: form.content,
        agent_enabled: form.agent_enabled,
        config: {
          workflow_keys: form.workflow_keys,
          skill_keys: form.skill_keys,
        },
        user_selectable: false,
      };
      if (editingId) await api.updateContent(editingId, payload);
      else { await api.createContent(payload); reset(); }
      await onRefresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "שמירת המומחה נכשלה");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (item: AgentContent) => {
    const confirmed = window.confirm(
      `למחוק את המומחה „${item.name}”? הפעולה אינה הפיכה.`,
    );
    if (!confirmed) return;
    setError("");
    try {
      await api.deleteContent(item.id);
      // The form would otherwise keep editing a row that no longer exists
      // and fail on the next save.
      if (editingId === item.id) reset();
      await onRefresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "מחיקת המומחה נכשלה");
    }
  };

  return (
    <div className="studio-split specialist-studio">
      <SpecialistList items={items} onEdit={edit} onRemove={remove}
        onNew={startNew} />
      <SpecialistFormView form={form} update={update} workflows={workflows}
        skills={skills} save={save} saving={saving} error={error}
        editing={!!editingId} reset={startNew} />
    </div>
  );
}

function SpecialistList({
  items, onEdit, onRemove, onNew,
}: {
  items: AgentContent[];
  onEdit: (item: AgentContent) => void;
  onRemove: (item: AgentContent) => void;
  onNew: () => void;
}) {
  return (
    <section className="studio-list">
      <header><h3>מומחים</h3>
        <div className="studio-list-actions">
          <span>{items.length} מומחים</span>
          <NewItemButton label="מומחה חדש" onClick={onNew} />
        </div>
      </header>
      {!items.length && <p className="panel-empty">
        <Bot size={18} aria-hidden="true" /> עדיין לא הוגדרו מומחים.
      </p>}
      {items.map((item) => <article key={item.id}
        className={`specialist-card${item.agent_enabled ? "" : " is-off"}`}>
        <button type="button" className="specialist-card-main"
          onClick={() => onEdit(item)}>
          <span className="catalog-icon"><Bot size={17} aria-hidden="true" /></span>
          <span><strong>{item.name}</strong><small>
            {item.agent_enabled ? "פעיל לסוכן" : "כבוי"}
            {` · ${item.config?.workflow_keys.length ?? 0} Workflows`}
            {item.config?.skill_keys.length
              ? ` · ${item.config.skill_keys.length} Skills` : ""}
          </small></span>
          <span className={`status-dot ${item.agent_enabled ? "on" : "off"}`} />
        </button>
        <div className="content-card-actions">
          <button type="button" className="danger-action"
            onClick={() => onRemove(item)}
            aria-label={`מחיקת המומחה ${item.name}`}>
            <Trash2 size={15} aria-hidden="true" /> מחיקה
          </button>
        </div>
      </article>)}
    </section>
  );
}

function SpecialistFormView({
  form, update, workflows, skills, save, saving, error, editing, reset,
}: {
  form: SpecialistForm;
  update: (patch: Partial<SpecialistForm>) => void;
  workflows: WorkflowVersion[];
  skills: AgentContent[];
  save: (event: FormEvent) => Promise<void>;
  saving: boolean;
  error: string;
  editing: boolean;
  reset: () => void;
}) {
  return (
    <form className="studio-form specialist-form" onSubmit={save}>
      <header className="studio-form-header">
        <span><Bot size={19} aria-hidden="true" /></span><div>
        <h3>{editing ? "עריכת מומחה" : "מומחה חדש"}</h3>
        <p>המנהל מאציל משימה; רק המומחה מפעיל את ה־Workflows שהוקצו לו.</p>
      </div>
        <SpecialistPlanChat form={form}
          onApply={(draft: SpecialistPlanDraft) => update(draft)} />
      </header>
      <div className="form-grid two">
        <label><span>שם המומחה *</span><input value={form.name}
          placeholder="לדוגמה: מומחה Geo"
          onChange={(event) => update({ name: event.target.value })} /></label>
        <label><span>תחום אחריות</span><input value={form.description}
          placeholder="מתי המנהל צריך לבחור במומחה"
          onChange={(event) => update({ description: event.target.value })} /></label>
      </div>
      <label className="agent-tool-toggle">
        <input type="checkbox" checked={form.agent_enabled}
          onChange={(event) => update({ agent_enabled: event.target.checked })} />
        <span>פעיל לסוכן
          <small>כשכבוי, המומחה נשמר וניתן לעריכה אך המנהל לא יאציל לו —
            ובדיקת התלויות הפעילות אינה חלה, כך שאפשר לשמור עבודה שלא הושלמה.</small>
        </span>
      </label>
      <label><span>הנחיות המומחה *</span>
        <textarea className="content-editor" rows={10} value={form.content}
          placeholder="הגדר מה לבדוק, איך לנתח, אילו פערים להציף ואיך לדווח למנהל."
          onChange={(event) => update({ content: event.target.value })} />
      </label>
      <CapabilityPicker icon={Workflow} legend="Workflows מורשים *"
        hint="אלו הכלים של המומחה. בזמן ריצה הוא יבחר רק את המעט שנדרש למשימה."
        empty="אין Workflows זמינים. יש ליצור Workflow קודם."
        options={workflows.map((workflow) => ({
          key: workflow.workflow_key,
          name: workflow.name,
          description: workflow.description,
          enabled: workflow.agent_enabled,
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
          enabled: skill.agent_enabled,
        }))}
        selected={form.skill_keys}
        onChange={(skill_keys) => update({ skill_keys })} />
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="specialist-form-note">
        כל Workflow יכול להיות בבעלות מומחה אחד בלבד. שמירה של מומחה
        פעיל בודקת שה־Workflows וה־Skills שבחרת פעילים גם הם.
      </div>
      <div className="form-actions">
        {editing && <button type="button" className="secondary-button"
          onClick={reset}>ביטול</button>}
        <button type="submit" className="primary-button"
          disabled={saving || !form.name.trim() || !form.content.trim()
            || !form.workflow_keys.length}>
          {saving
            ? <LoaderCircle className="spin" size={17} aria-hidden="true" />
            : <Save size={17} aria-hidden="true" />}
          {saving ? "שומר…" : editing ? "שמירת שינויים" : "שמירה"}
        </button>
      </div>
    </form>
  );
}

interface CapabilityOption {
  key: string;
  name: string;
  description: string;
  enabled: boolean;
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
              <small>{option.enabled ? "פעיל" : "כבוי"}
                {" · "}<bdi dir="ltr">{option.key}</bdi></small>
            </span>
          </label>;
        })}
      </div>
    </fieldset>
  );
}
