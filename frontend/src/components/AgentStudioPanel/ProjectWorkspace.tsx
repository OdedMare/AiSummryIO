"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import {
  Bot, BookOpen, FolderKanban, LoaderCircle, Save, Sparkles,
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
  items, activeProjectId, onSelectProject,
  packages,
  workflows,
  content,
  onRefresh,
  onNavigate,
}: {
  items: Project[];
  activeProjectId: string;
  onSelectProject: (projectId: string) => void;
  packages: PackageVersion[];
  workflows: WorkflowVersion[];
  content: AgentContent[];
  onRefresh: () => Promise<void>;
  onNavigate: (tab: CatalogTab) => void;
}) {
  const initialProject = items.find((item) => item.id === activeProjectId);
  const [form, setForm] = useState<ProjectDraft>(
    initialProject ? projectDraft(initialProject) : emptyProject,
  );
  const [editingId, setEditingId] = useState(initialProject?.id ?? "");
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);

  const selected = items.find((item) => item.id === editingId) ?? null;
  const skills = content.filter((item) => item.kind === "skill");
  const agents = content.filter((item) => item.kind === "agent");

  const edit = (item: Project) => {
    onSelectProject(item.id);
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
      onSelectProject(saved.id);
      setForm(projectDraft(saved));
      setNotice("הפרויקט נשמר.");
      await onRefresh();
      onSelectProject(saved.id);
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
    if (!window.confirm(
      `למחוק את הפרויקט „${item.name}” ואת כל הטולים, התהליכים, ה־Skills והסוכנים שלו?`,
    )) {
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
    const skill = await api.createContent(editingId, {
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
        <ProjectHeader editing={!!editingId} system={!!selected?.is_system} />
        <section className="project-brief" aria-labelledby="project-brief-title">
          <div>
            <span className="studio-kicker">Project brief</span>
            <h3 id="project-brief-title">המשימה שמכוונת את סביבת העבודה</h3>
            <p>כל היכולות שנוצרות בפרויקט שייכות רק לו ונמחקות יחד איתו.</p>
          </div>
          <div className="project-brief-fields">
            <label><span>שם הפרויקט *</span>
              <input value={form.name} maxLength={120}
                placeholder="לדוגמה: בדיקת עסקאות חריגות"
                readOnly={!!selected?.is_system}
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
            {editingId && selected && <MissionSkillAssistant projectId={editingId}
              project={{ ...selected, ...form }} open={assistantOpen}
              onOpen={() => setAssistantOpen(true)}
              onClose={() => setAssistantOpen(false)}
              onAttach={attachMissionSkill} />}
          </div>
        </section>

        <div className="project-capability-grid">
          <CapabilityLink icon={Wrench} title="טולים" count={packages.length}
            onManage={() => onNavigate("packages")} />
          <CapabilityLink icon={Workflow} title="Workflows" count={workflows.length}
            onManage={() => onNavigate("workflows")} />
          <CapabilityLink icon={BookOpen} title="Skills" count={skills.length}
            onManage={() => onNavigate("content")} />
          <CapabilityLink icon={Bot} title="Agents" count={agents.length}
            onManage={() => onNavigate("specialists")} />
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

function ProjectHeader({ editing, system }: { editing: boolean; system: boolean }) {
  return (
    <header className="project-workspace-header">
      <span><FolderKanban size={20} aria-hidden="true" /></span>
      <div>
        <span className="studio-kicker">Mission workspace</span>
        <h2>{system ? "פרויקט המערכת" : editing ? "סביבת הפרויקט" : "פרויקט חדש"}</h2>
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
              <small>{item.is_system ? "הפרויקט הקיים · " : ""}{count} יכולות · עודכן {new Date(item.updated_at).toLocaleDateString("he-IL")}</small>
            </span>
          </button>
          {!item.is_system && <button type="button" className="catalog-card-delete"
            onClick={() => onRemove(item)} aria-label={`מחיקת ${item.name}`}>
            <Trash2 size={15} aria-hidden="true" />
          </button>}
        </article>;
      })}
    </section>
  );
}

function CapabilityLink({
  icon: Icon, title, count, onManage,
}: {
  icon: LucideIcon;
  title: string;
  count: number;
  onManage: () => void;
}) {
  return (
    <section className="project-capability">
      <div className="project-capability-head">
        <p><Icon size={17} aria-hidden="true" /> {title}: {count}</p>
        <button type="button" onClick={onManage}>ניהול</button>
      </div>
      {!count && <p className="capability-empty">אין עדיין פריטים בפרויקט.</p>}
    </section>
  );
}

function MissionSkillAssistant({
  projectId, project, open, onOpen, onClose, onAttach,
}: {
  projectId: string;
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
    (messages, draft) => api.planSkillChat(
      messages, { ...seed, ...(draft ?? {}) }, projectId,
    ),
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
