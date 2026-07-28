import {
  AlertTriangle, Clock3, LoaderCircle, Sparkles,
} from "lucide-react";
import BrandMark from "@/components/AppShell/BrandMark";
import type { SummaryRun, SummarySection, SummarySkill } from "@/types";
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

/** One continuous answer rather than a card per workflow. Sections are merged
    into the prose and reappear below as sources, so a reader follows a single
    thread instead of reassembling one from stacked panels. */
export function SummaryContent({ run }: { run: SummaryRun }) {
  const result = run.result;
  const sections = result?.sections ?? run.progress.sections ?? [];
  const synthesized = Boolean(result?.summary);
  return (
    <>
      {run.error && <div className="error-banner" role="alert">{run.error}</div>}
      <article className="answer-body">
        {result?.headline && <p className="answer-headline">{result.headline}</p>}
        {synthesized
          ? <p>{result?.summary}</p>
          : <PendingAnswer run={run} sections={sections} />}
        {result?.coverage && <p className="answer-coverage">{result.coverage}</p>}
        <AnswerList items={result?.key_findings ?? []} />
        <AnswerList title="סיכונים" tone="risk" items={result?.risks ?? []} />
        <AnswerList title="מידע חסר" tone="gap"
          items={result?.missing_data ?? []} />
        <Warnings sections={synthesized ? sections : []} />
      </article>
      <SkillResults items={result?.skill_results ?? []} />
    </>
  );
}

/** Before synthesis finishes, `result` is null while sections stream in. Their
    summaries are the answer so far, so the prose assembles as they land rather
    than staying blank and popping in whole. */
function PendingAnswer(
  { run, sections }: { run: SummaryRun; sections: SummarySection[] },
) {
  const active = run.status === "queued" || run.status === "running";
  const arrived = sections.filter((section) => section.summary);
  if (!arrived.length) {
    return active
      ? <p className="answer-pending"><LoaderCircle className="spin" size={15} />
        אוסף מידע מהמקורות…
      </p>
      : null;
  }
  return (
    <>
      {arrived.map((section) =>
        <p key={section.workflow_id}>{section.summary}</p>)}
      {active && <p className="answer-pending">
        <LoaderCircle className="spin" size={15} /> ממשיך לאסוף…
      </p>}
    </>
  );
}

/** Findings, risks and gaps read as part of the answer, so they are plain
    lists in the flow — not tiles or bordered blocks beside it. */
function AnswerList(
  { title, tone, items }: { title?: string; tone?: string; items: string[] },
) {
  if (!items.length) return null;
  return (
    <div className={`answer-list ${tone ?? ""}`}>
      {title && <h3>{title}</h3>}
      <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
    </div>
  );
}

/** Section warnings lost their card, so they collect here instead of vanishing:
    a partial source has to say so somewhere in the answer. */
function Warnings({ sections }: { sections: SummarySection[] }) {
  const items = sections.flatMap((section) =>
    section.warnings.map((warning) => ({
      key: `${section.workflow_id}:${warning}`,
      name: section.name,
      warning,
    })));
  const degraded = sections.some((section) => section.degraded);
  if (!items.length && !degraded) return null;
  return (
    <div className="answer-warnings" role="status">
      <h3><AlertTriangle size={15} aria-hidden="true" /> הסתייגויות</h3>
      <ul>
        {degraded && <li>חלק מהסיכום הופק ללא מודל השפה — ספירות בלבד.</li>}
        {items.map((item) =>
          <li key={item.key}><b>{item.name}:</b> {item.warning}</li>)}
      </ul>
    </div>
  );
}
