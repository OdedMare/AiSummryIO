import { Check, LoaderCircle } from "lucide-react";
import type { SummaryRun, SummarySection } from "@/types";

/**
 * The agent working, as a chat message rather than a job readout.
 *
 * A status pill and a percentage bar describe a *run*; this describes what
 * the agent is doing, naming each source as it lands. The information is the
 * same — it is the framing that makes the thread read as a conversation
 * rather than as a queue the user is watching.
 *
 * Sections stream in through `progress`, so a source that has already
 * answered is shown resolved while the rest are still pending. Nothing is
 * rendered once the run finishes: the answer itself is then the status.
 */
export default function AgentStatus({ run }: { run: SummaryRun }) {
  const active = run.status === "queued" || run.status === "running";
  if (!active) return null;
  const sections = run.progress.sections ?? [];
  const { total } = run.progress;
  return (
    <div className="agent-status" role="status">
      <p className="agent-status-line">
        <LoaderCircle className="spin" size={15} aria-hidden="true" />
        {statusLabel(run, sections.length)}
      </p>
      {!!sections.length &&
        <ul className="agent-status-sources">
          {sections.map((section) => (
            <li key={section.workflow_id}>
              <Done section={section} /> {section.name}
            </li>
          ))}
          {/* The sources still to come are known only by count, so they are
              one line rather than a list of blanks pretending to be names. */}
          {total > sections.length &&
            <li className="pending">
              <LoaderCircle className="spin" size={13} aria-hidden="true" />
              עוד {total - sections.length} מקורות
            </li>}
        </ul>}
    </div>
  );
}

function Done({ section }: { section: SummarySection }) {
  const complete = section.status === "completed";
  return (
    <span className={`agent-status-dot ${section.status}`}>
      {complete
        ? <Check size={13} aria-hidden="true" />
        : <span className="agent-status-warn" aria-hidden="true">!</span>}
    </span>
  );
}

/** What the agent says it is doing, in the user's terms rather than the
    queue's. "ממתין בתור" is deliberately absent — the user asked a question
    and is owed an answer about their question, not about our scheduler. */
function statusLabel(run: SummaryRun, arrived: number): string {
  if (run.status === "queued") return "הסוכן מתחיל…";
  if (!arrived) return "הסוכן אוסף מידע מהמקורות…";
  return "הסוכן מנסח את התשובה…";
}
