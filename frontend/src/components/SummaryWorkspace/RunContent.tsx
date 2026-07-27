import {
  CheckCircle2, Clock3, LoaderCircle, Sparkles,
} from "lucide-react";
import BrandMark from "@/components/AppShell/BrandMark";
import type { SummaryRun, SummarySkill } from "@/types";
import SectionCard from "./SectionCard";
import { SkillHint, SkillResults } from "./Skills";

export function EmptyWorkspace({ skills }: { skills: SummarySkill[] }) {
  return (
    <main id="main-workspace" className="workspace empty-workspace">
      <div className="empty-intro">
        <div className="empty-illustration"><BrandMark size={40} /></div>
        <span className="welcome-pill"><Sparkles size={14} />
          פשוט מתחילים ממזהה
        </span>
        <h1>כל מה שחשוב לדעת, <span className="hero-accent">בסיכום אחד
          ברור</span></h1>
        <p>הזינו מזהה בתיבה למטה. <b dir="ltr">SumOrAI</b> יאסוף את המידע,
          יסביר אותו בעברית ויראה על אילו מקורות הסתמך.</p>
      </div>
      <SkillHint skills={skills} />
    </main>
  );
}

export function RunHeader({ run }: { run: SummaryRun }) {
  const active = run.status === "queued" || run.status === "running";
  return (
    <header className="workspace-header">
      <div><span className={`run-pill ${run.status}`}>
        {active && <LoaderCircle className="spin" size={14} />}
        {statusLabel(run.status)}
      </span>
        <h1>{run.kind === "full" ? "הסיכום המלא" : "תשובת המשך"}</h1>
      </div>
      {run.progress.total > 0 &&
        <div className="progress-copy"><Clock3 size={16} />
          {run.progress.completed} מתוך {run.progress.total} תהליכים
        </div>}
    </header>
  );
}

function statusLabel(status: SummaryRun["status"]) {
  const labels = {
    queued: "ממתין", running: "מעבד", completed: "הושלם",
    partial: "הושלם חלקית", failed: "נכשל",
  };
  return labels[status];
}

export function RunProgress({ run }: { run: SummaryRun }) {
  const active = run.status === "queued" || run.status === "running";
  if (!active || !run.progress.total) return null;
  const width = (run.progress.completed / run.progress.total) * 100;
  return (
    <div className="progress-track" role="progressbar" aria-valuemin={0}
      aria-valuemax={run.progress.total} aria-valuenow={run.progress.completed}>
      <span style={{ width: `${width}%` }} />
    </div>
  );
}

export function SummaryContent({ run }: { run: SummaryRun }) {
  const sections = run.result?.sections ?? run.progress.sections ?? [];
  return (
    <>
      {run.error && <div className="error-banner" role="alert">{run.error}</div>}
      {run.result?.summary &&
        <section className="executive-summary">
          <span className="eyebrow">תמונה כוללת</span>
          <p>{run.result.summary}</p>
        </section>}
      <Findings items={run.result?.key_findings ?? []} />
      <SkillResults items={run.result?.skill_results ?? []} />
      <section className="section-stack" aria-label="חלקי הסיכום">
        {sections.map((section) =>
          <SectionCard key={section.workflow_id} section={section} />)}
      </section>
    </>
  );
}

function Findings({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <section className="finding-grid">
      {items.map((finding) =>
        <div key={finding}><CheckCircle2 size={18} /><span>{finding}</span></div>)}
    </section>
  );
}
