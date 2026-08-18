"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import {
  Bot, BookOpen, Check, FolderKanban, LoaderCircle, Save, Sparkles,
  Trash2, Workflow, Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "@/services/api";
import type {
  AgentContent, PackageVersion, ProjectDraft, ProjectWorkspace as Project,
  SkillPlanDraft, WorkflowVersion,
} from "@/types";
import { PlanChat, PlanChatDrawer, usePlanChat } from "./PlanChat";
import { NewItemButton } from "./StudioCommon";

type CatalogTab = "packages" | "workflows" | "specialists" | "content";

const emptyProject: ProjectDraft = {
  name: "",
  mission: "",
  tool_keys: [],
  workflow_keys: [],
  skill_keys: [],
  agent_keys: [],
};

export default function ProjectWorkspace({
  items,
  packages,
  workflows,
  content,
  onRefresh,
  onNavigate,
}: {
  items: Project[];
  packages: PackageVersion[];
  workflows: WorkflowVersion[];
  content: AgentContent[];
  onRefresh: () => Promise<void>;
  onNavigate: (tab: CatalogTab) => void;
}) {
  const [form, setForm] = useState<ProjectDraft>(emptyProject);
  const [editingId, setEditingId] = useState("");
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);

  const selected = items.find((item) => item.id === editingId) ?? null;
  const skills = content.filter((item) => item.kind === "skill");
  const agents = content.filter((item) => item.kind === "agent");

  const edit = (item: Project) => {
    setEditingId(item.id);
    setForm(projectDraft(item));
    setError("");
    setNotice("");
    setAssistantOpen(false);
  };
  const startNew = () => {
    setEditingId("");
    setForm(emptyProject);
    setError("");
    setNotice("");
    setAssistantOpen(false);
  };
  const update = (patch: Partial<ProjectDraft>) =>
    setForm((current) => ({ ...current, ...patch }));

  const persist = async (startAssistant = false) => {
    if (!form.name.trim() || !form.mission.trim() || saving) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const saved = editingId
        ? await api.updateProject(editingId, form)
        : await api.createProject(form);
      setEditingId(saved.id);
      setForm(projectDraft(saved));
      setNotice("הפרויקט נשמר.");
      await onRefresh();
      if (startAssistant) setAssistantOpen(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "שמירת הפרויקט נכשלה");
    } finally {
      setSaving(false);
    }
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    await persist(false);
  };

  const remove = async (item: Project) => {
    if (!window.confirm(`למחוק את הפרויקט „${item.name}”? הקטלוג עצמו לא יימחק.`)) {
      return;
    }
    setError("");
    try {
      await api.deleteProject(item.id);
      if (editingId === item.id) startNew();
      await onRefresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "מחיקת הפרויקט נכשלה");
    }
  };

  const attachMissionSkill = async (draft: SkillPlanDraft) => {
    const skill = await api.createContent({
      kind: "skill",
      name: draft.name,
      description: draft.description,
      content: draft.content,
      user_selectable: draft.user_selectable,
      agent_enabled: draft.agent_enabled,
    });
    const next = {
      ...form,
      skill_keys: Array.from(new Set([...form.skill_keys, skill.content_key])),
    };
    const saved = await api.updateProject(editingId, next);
    setForm(projectDraft(saved));
    setNotice(`ה־Skill „${skill.name}” נוצר ושויך לפרויקט.`);
    await onRefresh();
  };

  return (
    <div className="project-studio">
      <ProjectList items={items} selectedId={editingId} onEdit={edit}
        onRemove={remove} onNew={startNew} />
      <form className="project-workspace" onSubmit={save}>
        <ProjectHeader editing={!!editingId} />
        <section className="project-brief" aria-labelledby="project-brief-title">
          <div>
            <span className="studio-kicker">Project brief</span>
            <h3 id="project-brief-title">המשימה שמכוונת את סביבת העבודה</h3>
            <p>הקטלוג נשאר מקור אמת אחד; הפרויקט בוחר רק מה שדרוש למשימה.</p>
          </div>
          <div className="project-brief-fields">
            <label><span>שם הפרויקט *</span>
              <input value={form.name} maxLength={120}
                placeholder="לדוגמה: בדיקת עסקאות חריגות"
                onChange={(event) => update({ name: event.target.value })} />
            </label>
            <label><span>משימת הפרויקט *</span>
              <textarea value={form.mission} maxLength={5000} rows={4}
                placeholder="איזו החלטה הפרויקט צריך לאפשר, עבור מי, ועל סמך אילו ראיות?"
                onChange={(event) => update({ mission: event.target.value })} />
            </label>
          </div>
          <div className="project-setup-actions">
            {!editingId && <button type="button" className="secondary-button"
              disabled={saving || !form.name.trim() || !form.mission.trim()}
              onClick={() => void persist(true)}>
              {saving
                ? <LoaderCircle className="spin" size={17} aria-hidden="true" />
                : <Sparkles size={17} aria-hidden="true" />}
              יצירה עם FDE
            </button>}
            {editingId && selected && <MissionSkillAssistant
              project={{ ...selected, ...form }} open={assistantOpen}
              onOpen={() => setAssistantOpen(true)}
              onClose={() => setAssistantOpen(false)}
              onAttach={attachMissionSkill} />}
          </div>
        </section>

        <div className="project-capability-grid">
          <CapabilitySection icon={Wrench} title="טולים" hint="מקורות הנתונים של הפרויקט"
            manageLabel="ניהול טולים" onManage={() => onNavigate("packages")}
            options={packages.map((item) => ({
              key: item.package_key, name: item.name,
              description: item.description, enabled: item.agent_enabled,
            }))}
            selected={form.tool_keys}
            onChange={(tool_keys) => update({ tool_keys })} />
          <CapabilitySection icon={Workflow} title="Workflows"
            hint="תהליכים שמחברים נתונים לתשובה"
            manageLabel="ניהול Workflows" onManage={() => onNavigate("workflows")}
            options={workflows.map((item) => ({
              key: item.workflow_key, name: item.name,
              description: item.description, enabled: item.agent_enabled,
            }))}
            selected={form.workflow_keys}
            onChange={(workflow_keys) => update({ workflow_keys })} />
          <CapabilitySection icon={BookOpen} title="Skills"
            hint="ניתוחים וניסוחים מותאמים למשימה"
            manageLabel="ניהול Skills" onManage={() => onNavigate("content")}
            options={skills.map((item) => ({
              key: item.content_key, name: item.name,
              description: item.description, enabled: item.agent_enabled,
            }))}
            selected={form.skill_keys}
            onChange={(skill_keys) => update({ skill_keys })} />
          <CapabilitySection icon={Bot} title="Agents"
            hint="המומחים שהמנהל יכול להפעיל"
            manageLabel="ניהול Agents" onManage={() => onNavigate("specialists")}
            options={agents.map((item) => ({
              key: item.content_key, name: item.name,
              description: item.description, enabled: item.agent_enabled,
            }))}
            selected={form.agent_keys}
            onChange={(agent_keys) => update({ agent_keys })} />
        </div>

        {error && <p className="form-error" role="alert">{error}</p>}
        {notice && <p className="project-notice" role="status">{notice}</p>}
        <div className="form-actions project-form-actions">
          {editingId && <button type="button" className="secondary-button"
            onClick={startNew}>פרויקט חדש</button>}
          <button type="submit" className="primary-button"
            disabled={saving || !form.name.trim() || !form.mission.trim()}>
            {saving
              ? <LoaderCircle className="spin" size={17} aria-hidden="true" />
              : <Save size={17} aria-hidden="true" />}
            {editingId ? "שמירת סביבת העבודה" : "יצירת פרויקט"}
          </button>
        </div>
      </form>
    </div>
  );
}

function ProjectHeader({ editing }: { editing: boolean }) {
  return (
    <header className="project-workspace-header">
      <span><FolderKanban size={20} aria-hidden="true" /></span>
      <div>
        <span className="studio-kicker">Mission workspace</span>
        <h2>{editing ? "סביבת הפרויקט" : "פרויקט חדש"}</h2>
        <p>בחרו את היכולות בעצמכם, או תנו לסוכן FDE לנסח Skill לפי המשימה.</p>
      </div>
    </header>
  );
}

function ProjectList({
  items, selectedId, onEdit, onRemove, onNew,
}: {
  items: Project[];
  selectedId: string;
  onEdit: (item: Project) => void;
  onRemove: (item: Project) => void;
  onNew: () => void;
}) {
  return (
    <section className="studio-list project-list">
      <header><h3>פרויקטים</h3>
        <div className="studio-list-actions">
          <span>{items.length} סביבות</span>
          <NewItemButton label="פרויקט חדש" onClick={onNew} />
        </div>
      </header>
      {!items.length && <p className="panel-empty">
        <FolderKanban size={18} aria-hidden="true" />
        התחילו ממשימה אחת; את היכולות אפשר להוסיף בהדרגה.
      </p>}
      {items.map((item) => {
        const count = item.tool_keys.length + item.workflow_keys.length
          + item.skill_keys.length + item.agent_keys.length;
        return <article key={item.id}
          className={`project-card${selectedId === item.id ? " selected" : ""}`}>
          <button type="button" className="project-card-main"
            onClick={() => onEdit(item)}>
            <span className="catalog-icon"><FolderKanban size={17} /></span>
            <span><strong title={item.name}>{item.name}</strong>
              <small>{count} יכולות · עודכן {new Date(item.updated_at).toLocaleDateString("he-IL")}</small>
            </span>
          </button>
          <button type="button" className="catalog-card-delete"
            onClick={() => onRemove(item)} aria-label={`מחיקת ${item.name}`}>
            <Trash2 size={15} aria-hidden="true" />
          </button>
        </article>;
      })}
    </section>
  );
}

interface CapabilityOption {
  key: string;
  name: string;
  description: string;
  enabled: boolean;
  missing?: boolean;
}

function CapabilitySection({
  icon: Icon, title, hint, options, selected, onChange, manageLabel, onManage,
}: {
  icon: LucideIcon;
  title: string;
  hint: string;
  options: CapabilityOption[];
  selected: string[];
  onChange: (keys: string[]) => void;
  manageLabel: string;
  onManage: () => void;
}) {
  const toggle = (key: string) => onChange(
    selected.includes(key)
      ? selected.filter((item) => item !== key)
      : [...selected, key],
  );
  const known = new Set(options.map((option) => option.key));
  const visibleOptions = [
    ...options,
    ...selected.filter((key) => !known.has(key)).map((key) => ({
      key,
      name: key,
      description: "הפריט כבר לא קיים בקטלוג",
      enabled: false,
      missing: true,
    })),
  ];
  return (
    <fieldset className="project-capability">
      <legend><Icon size={17} aria-hidden="true" /> {title}</legend>
      <div className="project-capability-head">
        <p>{hint}</p>
        <button type="button" onClick={onManage}>{manageLabel}</button>
      </div>
      {!options.length && <p className="capability-empty">אין עדיין פריטים בקטלוג.</p>}
      <div className="project-options">
        {visibleOptions.map((option) => {
          const active = selected.includes(option.key);
          return <label key={option.key}
            className={`${active ? "selected" : ""}${option.missing ? " missing" : ""}`}>
            <input type="checkbox" checked={active}
              onChange={() => toggle(option.key)} />
            <span className="capability-check" aria-hidden="true">
              {active && <Check size={14} />}
            </span>
            <span><strong title={option.name}>{option.name}</strong>
              <small title={option.description || option.key}>
                {option.description || option.key}
              </small>
              <small className={option.enabled ? "capability-live" : "capability-off"}>
                {option.missing
                  ? "לא קיים בקטלוג — הסירו לפני שמירה"
                  : option.enabled ? "פעיל לסוכן" : "כבוי — נשמר בפרויקט בלבד"}
              </small>
            </span>
          </label>;
        })}
      </div>
    </fieldset>
  );
}

function MissionSkillAssistant({
  project, open, onOpen, onClose, onAttach,
}: {
  project: Project;
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
  onAttach: (draft: SkillPlanDraft) => Promise<void>;
}) {
  const [applyError, setApplyError] = useState("");
  const [applying, setApplying] = useState(false);
  const seed: SkillPlanDraft = {
    // A Hebrew-only name lets the backend generate a fresh UUID key. An
    // English "Skill" prefix would slug every project to the same key.
    name: `מיומנות · ${project.name}`,
    description: `ניתוח מותאם למשימת ${project.name}`,
    content: "",
    user_selectable: true,
    agent_enabled: true,
  };
  const chat = usePlanChat<SkillPlanDraft>(
    (messages, draft) => api.planSkillChat(messages, { ...seed, ...(draft ?? {}) }),
    (readyDraft) => {
      setApplying(true);
      setApplyError("");
      void onAttach(readyDraft)
        .then(() => onClose())
        .catch((reason) => setApplyError(
          reason instanceof Error ? reason.message : "יצירת ה־Skill נכשלה",
        ))
        .finally(() => setApplying(false));
    },
  );

  return (
    <PlanChatDrawer open={open} onOpen={onOpen} onClose={onClose}
      label="FDE להתאמת Skill" busy={chat.pending || applying}
      disabled={!project.name.trim() || !project.mission.trim()}
      disabledHint="יש למלא שם ומשימה לפני פתיחת שיחת FDE">
      <PlanChat chat={chat} title={`FDE · ${project.name}`}
        hint="הסוכן מתחיל מהמשימה, שואל שאלה אחת בכל פעם, ומציע Skill מלא. רק אחרי האישור הוא יישמר וישויך לפרויקט.">
        {!chat.messages.length && !chat.pending && <button type="button"
          className="planner-button project-agent-start" onClick={() => void chat.send(
            `אני מקים את הפרויקט „${project.name}”. המשימה שלו היא: ${project.mission}. `
            + "נסח איתי Skill ייעודי שמכוון את הניתוח והתוצאה למשימה הזאת.",
          )}>
          <Sparkles size={16} aria-hidden="true" /> התחלה ממשימת הפרויקט
        </button>}
        {chat.draft && <div className="planner-result project-skill-preview">
          <strong>{chat.draft.name || "Skill למשימה"}</strong>
          <p>{chat.draft.description || "ההגדרה תופיע כאן במהלך השיחה."}</p>
        </div>}
        {applyError && <p className="form-error" role="alert">{applyError}</p>}
        {applying && <p className="loading-line">
          <LoaderCircle className="spin" size={15} /> שומר ומשייך לפרויקט…
        </p>}
      </PlanChat>
    </PlanChatDrawer>
  );
}

function projectDraft(project: Project): ProjectDraft {
  return {
    name: project.name,
    mission: project.mission,
    tool_keys: project.tool_keys,
    workflow_keys: project.workflow_keys,
    skill_keys: project.skill_keys,
    agent_keys: project.agent_keys,
  };
}
