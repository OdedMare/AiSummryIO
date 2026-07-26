"use client";

import { useState } from "react";
import {
  AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, Clock3,
  Database, FileText, LoaderCircle, ThumbsDown, ThumbsUp,
} from "lucide-react";
import { api } from "@/services/api";
import type { Evidence, SummaryRun, SummarySection } from "@/types";

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
  const [items, setItems] = useState<Evidence[] | null>(null);
  const [error, setError] = useState("");

  if (open && items === null && !error) {
    api.evidence(runId).then(setItems).catch((reason) => setError(reason.message));
  }
  if (!open) return null;
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
}: {
  run: SummaryRun | null;
}) {
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  const liveSections = run?.result?.sections ?? run?.progress.sections ?? [];
  const active = run?.status === "queued" || run?.status === "running";

  if (!run) {
    return (
      <main className="workspace empty-workspace">
        <div className="empty-illustration"><FileText size={36} /></div>
        <h1>סיכום מלא לפי מזהה</h1>
        <p>
          הזינו מזהה כדי להפעיל את כל תהליכי הבסיס. כל חלק יופיע ברגע שהוא מוכן.
        </p>
        <div className="empty-steps">
          <span>1</span><p>מזינים מזהה</p>
          <span>2</span><p>התהליכים אוספים ראיות</p>
          <span>3</span><p>מקבלים סיכום עברי מלא</p>
        </div>
      </main>
    );
  }

  return (
    <main className="workspace" aria-live="polite">
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

