"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle, BriefcaseBusiness, CalendarDays, Check, CheckCircle2,
  ChevronDown, ChevronUp, Clock3, Database, FileText, ListChecks,
  LoaderCircle, ShieldAlert, Sparkles, ThumbsDown, ThumbsUp,
} from "lucide-react";
import { api } from "@/services/api";
import type {
  Evidence, SkillResult, SummaryRun, SummarySection, SummarySkill,
} from "@/types";

const skillIcon = (key: string) => {
  if (key.includes("executive")) return BriefcaseBusiness;
  if (key.includes("risk")) return ShieldAlert;
  if (key.includes("action")) return ListChecks;
  if (key.includes("timeline")) return CalendarDays;
  return Sparkles;
};

function SkillPicker({
  skills,
  selected,
  onToggle,
}: {
  skills: SummarySkill[];
  selected: string[];
  onToggle: (key: string) => void;
}) {
  if (!skills.length) return null;
  return (
    <section className="skill-picker" aria-labelledby="skill-picker-title">
      <header>
        <div>
          <span className="eyebrow">לא חובה</span>
          <h2 id="skill-picker-title">מה תרצו לקבל מהסיכום?</h2>
          <p>כל Skill מפעיל ניתוח נוסף על המידע שנאסף.</p>
        </div>
        <span>{selected.length}/3 נבחרו</span>
      </header>
      <div className="skill-grid">
        {skills.map((skill) => {
          const active = selected.includes(skill.content_key);
          const Icon = skillIcon(skill.content_key);
          return (
            <button
              key={skill.content_key}
              type="button"
              className={active ? "skill-card active" : "skill-card"}
              onClick={() => onToggle(skill.content_key)}
              aria-pressed={active}
            >
              <span className="skill-card-icon"><Icon size={20} /></span>
              <span>
                <strong>{skill.name}</strong>
                <small>{skill.description}</small>
              </span>
              <span className="skill-check" aria-hidden="true">
                {active && <Check size={15} />}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function SkillResults({ items }: { items: SkillResult[] }) {
  if (!items.length) return null;
  return (
    <section className="skill-results" aria-labelledby="skill-results-title">
      <header>
        <span className="eyebrow">לפי הבחירה שלכם</span>
        <h2 id="skill-results-title">תוצרי ה־Skills</h2>
      </header>
      <div className="skill-result-grid">
        {items.map((item) => {
          const Icon = skillIcon(item.skill_key);
          return (
            <article className="skill-result-card" key={item.skill_key}>
              <header>
                <span><Icon size={19} /></span>
                <h3>{item.name}</h3>
              </header>
              <p>{item.summary}</p>
              {!!item.items.length && (
                <ul>{item.items.map((entry) => <li key={entry}>{entry}</li>)}</ul>
              )}
              {!!item.sources.length && (
                <small>מבוסס על: {item.sources.join(" · ")}</small>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function SectionCard({ section }: { section: SummarySection }) {
  const [open, setOpen] = useState(false);
  const Icon = section.status === "completed" ? CheckCircle2 : AlertTriangle;
  return (
    <article className="summary-section">
      <button
        className="section-toggle"
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <span className={`section-status ${section.status}`}>
          <Icon size={18} aria-hidden="true" />
        </span>
        <span>
          <strong>{section.name}</strong>
          <small>{section.status === "completed" ? "הושלם" : "כיסוי חלקי"}</small>
        </span>
        {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>
      <p>{section.summary}</p>
      {open && (
        <div className="section-details">
          {!!section.facts.length && (
            <ul>{section.facts.map((fact) => <li key={fact}>{fact}</li>)}</ul>
          )}
          {!!section.warnings.length && (
            <div className="warning-box" role="status">
              {section.warnings.map((warning) => <p key={warning}>{warning}</p>)}
            </div>
          )}
        </div>
      )}
    </article>
  );
}

function EvidenceDrawer({
  runId,
  open,
}: {
  runId: string;
  open: boolean;
}) {
  const [loaded, setLoaded] = useState<{
    runId: string;
    items: Evidence[];
    error: string;
  } | null>(null);

  useEffect(() => {
    if (!open) return;
    let current = true;
    api.evidence(runId)
      .then((next) => {
        if (current) setLoaded({ runId, items: next, error: "" });
      })
      .catch((reason) => {
        if (current) {
          setLoaded({ runId, items: [], error: reason.message });
        }
      });
    return () => {
      current = false;
    };
  }, [open, runId]);

  if (!open) return null;
  const items = loaded?.runId === runId ? loaded.items : null;
  const error = loaded?.runId === runId ? loaded.error : "";
  if (error) return <p role="alert">{error}</p>;
  if (!items) return <p className="loading-line"><LoaderCircle size={16} /> טוען ראיות…</p>;
  return (
    <div className="evidence-list">
      {items.map((item) => (
        <details key={item.id}>
          <summary>
            <Database size={16} aria-hidden="true" />
            {item.step_key} · {item.records.length} רשומות
          </summary>
          <pre dir="ltr">{JSON.stringify(item.records, null, 2)}</pre>
        </details>
      ))}
      {!items.length && <p>לא נשמרו ראיות לריצה זו.</p>}
    </div>
  );
}

export default function SummaryWorkspace({
  run,
  skills,
  selectedSkillKeys,
  onToggleSkill,
}: {
  run: SummaryRun | null;
  skills: SummarySkill[];
  selectedSkillKeys: string[];
  onToggleSkill: (key: string) => void;
}) {
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  const liveSections = run?.result?.sections ?? run?.progress.sections ?? [];
  const active = run?.status === "queued" || run?.status === "running";

  if (!run) {
    return (
      <main id="main-workspace" className="workspace empty-workspace">
        <div className="empty-intro">
          <div className="empty-illustration"><FileText size={36} /></div>
          <span className="welcome-pill"><Sparkles size={14} /> פשוט מתחילים ממזהה</span>
          <h1>כל מה שחשוב לדעת, בסיכום אחד ברור</h1>
          <p>
            הזינו מזהה בתיבה למטה. נאסוף את המידע, נסביר אותו בעברית
            ונראה על אילו מקורות הסתמכנו.
          </p>
        </div>
        <SkillPicker
          skills={skills}
          selected={selectedSkillKeys}
          onToggle={onToggleSkill}
        />
      </main>
    );
  }

  return (
    <main id="main-workspace" className="workspace" aria-live="polite">
      <header className="workspace-header">
        <div>
          <span className={`run-pill ${run.status}`}>
            {active && <LoaderCircle className="spin" size={14} />}
            {run.status === "queued" ? "ממתין" :
              run.status === "running" ? "מעבד" :
                run.status === "completed" ? "הושלם" :
                  run.status === "partial" ? "הושלם חלקית" : "נכשל"}
          </span>
          <h1>{run.kind === "full" ? "הסיכום המלא" : "תשובת המשך"}</h1>
        </div>
        {run.progress.total > 0 && (
          <div className="progress-copy">
            <Clock3 size={16} />
            {run.progress.completed} מתוך {run.progress.total} תהליכים
          </div>
        )}
      </header>

      {active && run.progress.total > 0 && (
        <div
          className="progress-track"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={run.progress.total}
          aria-valuenow={run.progress.completed}
        >
          <span style={{
            width: `${(run.progress.completed / run.progress.total) * 100}%`,
          }} />
        </div>
      )}

      {run.error && <div className="error-banner" role="alert">{run.error}</div>}

      {run.result?.summary && (
        <section className="executive-summary">
          <span className="eyebrow">תמונה כוללת</span>
          <p>{run.result.summary}</p>
        </section>
      )}

      {!!run.result?.key_findings.length && (
        <section className="finding-grid">
          {run.result.key_findings.map((finding) => (
            <div key={finding}><CheckCircle2 size={18} /><span>{finding}</span></div>
          ))}
        </section>
      )}

      <SkillResults items={run.result?.skill_results ?? []} />

      <section className="section-stack" aria-label="חלקי הסיכום">
        {liveSections.map((section) => (
          <SectionCard key={section.workflow_id} section={section} />
        ))}
      </section>

      {run.result && (
        <footer className="result-footer">
          <button
            type="button"
            className="secondary-button"
            onClick={() => setEvidenceOpen((value) => !value)}
          >
            <Database size={17} />
            {evidenceOpen ? "הסתרת ראיות" : "הצגת ראיות"}
          </button>
          <div className="feedback-actions" aria-label="משוב על הסיכום">
            <button
              type="button"
              className={feedback === "up" ? "active" : ""}
              onClick={() => {
                setFeedback("up");
                void api.feedback(run.id, 1);
              }}
              aria-label="הסיכום עזר לי"
            >
              <ThumbsUp size={17} />
            </button>
            <button
              type="button"
              className={feedback === "down" ? "active" : ""}
              onClick={() => {
                setFeedback("down");
                void api.feedback(run.id, -1);
              }}
              aria-label="הסיכום דורש שיפור"
            >
              <ThumbsDown size={17} />
            </button>
          </div>
        </footer>
      )}
      <EvidenceDrawer runId={run.id} open={evidenceOpen} />
    </main>
  );
}
