"use client";

import { Dispatch, SetStateAction, useState } from "react";
import { Database, ThumbsDown, ThumbsUp } from "lucide-react";
import { api } from "@/services/api";
import type { SummaryRun, SummarySection, SummarySkill } from "@/types";
import EvidenceDrawer from "./EvidenceDrawer";
import {
  EmptyWorkspace, RunHeader, RunProgress, SummaryContent,
} from "./RunContent";
import SourceRow from "./SourceRow";

export default function SummaryWorkspace({
  run, skills,
}: {
  run: SummaryRun | null;
  skills: SummarySkill[];
}) {
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [source, setSource] = useState<SummarySection | null>(null);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  if (!run) return <EmptyWorkspace skills={skills} />;
  const sections = run.result?.sections ?? run.progress.sections ?? [];
  /* A chip toggles its own evidence; picking another swaps the filter without
     closing the drawer. "הצגת ראיות" clears the filter back to the whole run. */
  const selectSource = (section: SummarySection) => {
    const same = source?.workflow_id === section.workflow_id;
    setSource(same && evidenceOpen ? null : section);
    setEvidenceOpen(!(same && evidenceOpen));
  };
  const toggleAll = () => {
    setSource(null);
    setEvidenceOpen((value) => !(value && !source));
  };
  return (
    <main id="main-workspace" className="workspace" aria-live="polite">
      <RunHeader run={run} />
      <RunProgress run={run} />
      <SummaryContent run={run} />
      <SourceRow sections={sections} onSelect={selectSource}
        activeId={evidenceOpen ? source?.workflow_id ?? null : null} />
      {run.result && <ResultFooter run={run}
        evidenceOpen={evidenceOpen && !source} toggleAll={toggleAll}
        feedback={feedback} setFeedback={setFeedback} />}
      <EvidenceDrawer runId={run.id} open={evidenceOpen}
        evidenceIds={source?.evidence_ids} title={source?.name} />
    </main>
  );
}

function ResultFooter({
  run, evidenceOpen, toggleAll, feedback, setFeedback,
}: {
  run: SummaryRun;
  evidenceOpen: boolean;
  toggleAll: () => void;
  feedback: "up" | "down" | null;
  setFeedback: Dispatch<SetStateAction<"up" | "down" | null>>;
}) {
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
