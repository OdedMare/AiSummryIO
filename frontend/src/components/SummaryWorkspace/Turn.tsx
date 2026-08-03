import { Dispatch, SetStateAction, useState } from "react";
import { Database, ThumbsDown, ThumbsUp } from "lucide-react";
import { api } from "@/services/api";
import type { SummaryRun, SummarySection } from "@/types";
import EvidenceDrawer from "./EvidenceDrawer";
import { RunHeader, RunProgress, SummaryContent } from "./RunContent";
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
  run, view, setView, first,
}: {
  run: SummaryRun;
  view: EvidenceView | null;
  setView: Dispatch<SetStateAction<EvidenceView | null>>;
  first: boolean;
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
      <RunProgress run={run} />
      <SummaryContent run={run} />
      <SourceRow sections={sections} onSelect={selectSource}
        activeId={open ? source?.workflow_id ?? null : null} />
      {run.result && <TurnFooter run={run} evidenceOpen={open && !source}
        toggleAll={toggleAll} />}
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
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  const sendFeedback = (value: "up" | "down", rating: 1 | -1) => {
    setFeedback(value); void api.feedback(run.id, rating);
  };
  return (
    <footer className="result-footer">
      <button type="button" className="secondary-button" onClick={toggleAll}>
        <Database size={17} />
        {evidenceOpen ? "הסתרת ראיות" : "הצגת ראיות"}
      </button>
      <div className="feedback-actions" aria-label="משוב על הסיכום">
        <button type="button" className={feedback === "up" ? "active" : ""}
          onClick={() => sendFeedback("up", 1)} aria-label="הסיכום עזר לי">
          <ThumbsUp size={17} />
        </button>
        <button type="button" className={feedback === "down" ? "active" : ""}
          onClick={() => sendFeedback("down", -1)} aria-label="הסיכום דורש שיפור">
          <ThumbsDown size={17} />
        </button>
      </div>
    </footer>
  );
}
