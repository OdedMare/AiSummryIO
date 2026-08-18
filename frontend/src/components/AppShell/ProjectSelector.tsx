import {
  ArrowLeft, Bot, BookOpen, FolderKanban, LoaderCircle, Moon, Settings2,
  Sun, Workflow, Wrench,
} from "lucide-react";
import type { ProjectWorkspace } from "@/types";
import BrandMark from "./BrandMark";

export default function ProjectSelector({
  projects, loading, error, dark, onSelect, onManage, onRetry, onToggleTheme,
}: {
  projects: ProjectWorkspace[];
  loading: boolean;
  error: string;
  dark: boolean;
  onSelect: (project: ProjectWorkspace) => void;
  onManage: () => void;
  onRetry: () => void;
  onToggleTheme: () => void;
}) {
  return (
    <main className="project-selector" id="main-workspace">
      <header className="project-selector-topbar">
        <div className="project-selector-brand">
          <span className="brand-mark"><BrandMark size={22} /></span>
          <span><strong dir="ltr" className="brand-word">Sum<em>Or</em>AI</strong>
            <small>סביבות עבודה לפי משימה</small></span>
        </div>
        <button type="button" className="project-selector-icon-button"
          onClick={onToggleTheme}
          aria-label={dark ? "מעבר למצב בהיר" : "מעבר למצב כהה"}>
          {dark ? <Sun size={19} /> : <Moon size={19} />}
        </button>
      </header>

      <section className="project-selector-content" aria-labelledby="project-title">
        <div className="project-selector-intro">
          <span className="project-selector-icon"><FolderKanban size={25} /></span>
          <span className="eyebrow">Project workspace</span>
          <h1 id="project-title">באיזה פרויקט עובדים עכשיו?</h1>
          <p>כל פרויקט טוען את ה־Skills, הטולים, ה־Workflows והסוכנים
            ששייכים למשימה שלו.</p>
        </div>

        {loading && <p className="project-selector-status" role="status">
          <LoaderCircle className="spin" size={18} /> טוען פרויקטים…
        </p>}
        {!loading && error && <div className="project-selector-error" role="alert">
          <p>{error}</p>
          <button type="button" className="secondary-button" onClick={onRetry}>
            ניסיון נוסף
          </button>
        </div>}
        {!loading && !error && <div className="project-selector-grid">
          {projects.map((project) => <ProjectCard key={project.id}
            project={project} onSelect={() => onSelect(project)} />)}
        </div>}

        <footer className="project-selector-footer">
          <button type="button" className="secondary-button" onClick={onManage}>
            <Settings2 size={17} aria-hidden="true" /> ניהול ויצירת פרויקטים
          </button>
          <p>הקטלוג נשאר מקור אמת אחד; כל פרויקט בוחר מתוכו את היכולות שלו.</p>
        </footer>
      </section>
    </main>
  );
}

function ProjectCard({
  project, onSelect,
}: {
  project: ProjectWorkspace;
  onSelect: () => void;
}) {
  return (
    <article className={`project-choice-card${project.is_system ? " is-system" : ""}`}>
      <header>
        <span className="project-choice-folder"><FolderKanban size={21} /></span>
        {project.is_system && <span className="project-system-badge">
          הפרויקט הקיים
        </span>}
      </header>
      <div>
        <h2 dir={project.name === "Hunger Games" ? "ltr" : undefined}>
          {project.name}
        </h2>
        <p>{project.mission}</p>
      </div>
      <ul aria-label={`יכולות בפרויקט ${project.name}`}>
        <li><Wrench size={15} /><span>{project.tool_keys.length} טולים</span></li>
        <li><Workflow size={15} /><span>{project.workflow_keys.length} Workflows</span></li>
        <li><BookOpen size={15} /><span>{project.skill_keys.length} Skills</span></li>
        <li><Bot size={15} /><span>{project.agent_keys.length} Agents</span></li>
      </ul>
      <button type="button" className="project-choice-enter" onClick={onSelect}
        aria-label={`כניסה לפרויקט ${project.name}`}>
        כניסה לפרויקט <ArrowLeft size={17} aria-hidden="true" />
      </button>
    </article>
  );
}
