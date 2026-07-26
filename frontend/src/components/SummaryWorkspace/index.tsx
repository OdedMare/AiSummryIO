"use client";

import { Dispatch, SetStateAction, useState } from "react";
import { Database, ThumbsDown, ThumbsUp } from "lucide-react";
import { api } from "@/services/api";
import type { SummaryRun, SummarySkill } from "@/types";
import EvidenceDrawer from "./EvidenceDrawer";
import {
  EmptyWorkspace, RunHeader, RunProgress, SummaryContent,
} from "./RunContent";

export default function SummaryWorkspace({
  run, skills, selectedSkillKeys, onToggleSkill,
}: {
  run: SummaryRun | null;
  skills: SummarySkill[];
  selectedSkillKeys: string[];
  onToggleSkill: (key: string) => void;
}) {
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  if (!run) {
    return <EmptyWorkspace skills={skills} selected={selectedSkillKeys}
      onToggle={onToggleSkill} />;
  }
  return (
    <main id="main-workspace" className="workspace" aria-live="polite">
      <RunHeader run={run} />
      <RunProgress run={run} />
      <SummaryContent run={run} />
      {run.result && <ResultFooter run={run} evidenceOpen={evidenceOpen}
        setEvidenceOpen={setEvidenceOpen} feedback={feedback}
        setFeedback={setFeedback} />}
      <EvidenceDrawer runId={run.id} open={evidenceOpen} />
    </main>
  );
}

function ResultFooter({
  run, evidenceOpen, setEvidenceOpen, feedback, setFeedback,
}: {
  run: SummaryRun;
  evidenceOpen: boolean;
  setEvidenceOpen: Dispatch<SetStateAction<boolean>>;
  feedback: "up" | "down" | null;
  setFeedback: Dispatch<SetStateAction<"up" | "down" | null>>;
}) {
  const sendFeedback = (value: "up" | "down", rating: 1 | -1) => {
    setFeedback(value); void api.feedback(run.id, rating);
  };
  return (
    <footer className="result-footer">
      <button type="button" className="secondary-button"
        onClick={() => setEvidenceOpen((value) => !value)}>
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
