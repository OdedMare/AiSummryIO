import { Dispatch, SetStateAction, useState } from "react";
import { Database, Star } from "lucide-react";
import { api } from "@/services/api";
import type { SummaryRun, SummarySection } from "@/types";
import AgentStatus from "./AgentStatus";
import EvidenceDrawer from "./EvidenceDrawer";
import NextQuestions from "./NextQuestions";
import { RunHeader, SummaryContent } from "./RunContent";
import SourceRow from "./SourceRow";

/** Which turn has its evidence open, and filtered to which section. Held by
    the thread rather than per turn, so opening one closes another instead of
    leaving several drawers stacked down the page. */
export interface EvidenceView {
  runId: string;
  section: SummarySection | null;
}

/**
 * One question and the answer to it.
 *
 * The user's question is rendered above the answer because a transcript that
 * shows only answers forces the reader to remember what was asked. A `full`
 * run keeps its original header — it is the opening summary, not a reply.
 */
export default function Turn({
  run, view, setView, first, last, onAsk,
}: {
  run: SummaryRun;
  view: EvidenceView | null;
  setView: Dispatch<SetStateAction<EvidenceView | null>>;
  first: boolean;
  /** The newest turn, which is the only one still worth continuing from. */
  last: boolean;
  /** Asks a suggested question straight away, without the composer. */
  onAsk: (question: string) => void;
}) {
  const sections = run.result?.sections ?? run.progress.sections ?? [];
  const open = view?.runId === run.id;
  const source = open ? view?.section ?? null : null;

  /* A chip toggles its own evidence; picking another swaps the filter without
     closing the drawer. "הצגת ראיות" clears the filter back to the whole run. */
  const selectSource = (section: SummarySection) => {
    const same = open && source?.workflow_id === section.workflow_id;
    setView(same ? null : { runId: run.id, section });
  };
  const toggleAll = () => {
    setView(open && !source ? null : { runId: run.id, section: null });
  };

  return (
    <article className="thread-turn">
      {run.question && <Question text={run.question} />}
      {first && <RunHeader run={run} />}
      <AgentStatus run={run} />
      <SummaryContent run={run} />
      <SourceRow sections={sections} onSelect={selectSource}
        activeId={open ? source?.workflow_id ?? null : null} />
      {run.result && <TurnFooter run={run} evidenceOpen={open && !source}
        toggleAll={toggleAll} />}
      {/* Offered only on the newest turn: chips under an older answer would
          invite the user to reopen a question the thread has moved past. */}
      {run.result && last &&
        <NextQuestions result={run.result} onAsk={onAsk} />}
      <EvidenceDrawer runId={run.id} open={open}
        evidenceIds={source?.evidence_ids} title={source?.name} />
    </article>
  );
}

function Question({ text }: { text: string }) {
  return (
    <div className="thread-question">
      <p>{text}</p>
    </div>
  );
}

function TurnFooter({
  run, evidenceOpen, toggleAll,
}: {
  run: SummaryRun;
  evidenceOpen: boolean;
  toggleAll: () => void;
}) {
  /* Feedback is per answer, so it lives with the turn it rates rather than
     once at the bottom of the thread. */
  const [rating, setRating] = useState<1 | 2 | 3 | 4 | 5 | null>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  const sendRating = (value: 1 | 2 | 3 | 4 | 5) => {
    setRating(value); void api.feedback(run.id, value);
  };
  /* Hovering/focusing a star previews it and every star before it, the way a
     star widget is expected to read; it falls back to the sent rating once
     the pointer leaves. */
  const shown = hovered ?? rating ?? 0;
  return (
    <footer className="result-footer">
      <button type="button" className="secondary-button" onClick={toggleAll}>
        <Database size={17} />
        {evidenceOpen ? "הסתרת ראיות" : "הצגת ראיות"}
      </button>
      <div className="feedback-actions" role="radiogroup" aria-label="דירוג הסיכום, מכוכב אחד עד חמישה">
        {([1, 2, 3, 4, 5] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={rating === value}
            aria-label={"דירוג " + value + " מתוך 5 כוכבים"}
            className={value <= shown ? "active" : ""}
            onClick={() => sendRating(value)}
            onMouseEnter={() => setHovered(value)}
            onMouseLeave={() => setHovered(null)}
            onFocus={() => setHovered(value)}
            onBlur={() => setHovered(null)}
          >
            <Star size={17} fill={value <= shown ? "currentColor" : "none"} />
          </button>
        ))}
      </div>
    </footer>
  );
}
