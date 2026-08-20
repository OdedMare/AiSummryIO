"use client";

import { useEffect, useRef, useState } from "react";
import type { SummaryRun, SummarySkill } from "@/types";
import { EmptyWorkspace } from "./RunContent";
import Turn, { EvidenceView } from "./Turn";

/**
 * The conversation as a transcript: every question with the answer it got.
 *
 * Rendering only the latest run made a follow-up look like a replacement for
 * the summary before it, which is exactly what a thread is not. `runs` is the
 * whole conversation; `run` is only the turn still being polled, and is the
 * fallback while a brand-new conversation has yet to load its thread.
 */
export default function SummaryWorkspace({
  runs, run, skills, onAsk, onCitationSelected,
}: {
  runs: SummaryRun[];
  run: SummaryRun | null;
  skills: SummarySkill[];
  onAsk: (question: string) => void;
  /** Reports which citation the reader has open, so a follow-up asked while
      a source is selected can carry its id. */
  onCitationSelected?: (citationId: string | null) => void;
}) {
  const [view, setView] = useState<EvidenceView | null>(null);
  const selectedCitationId = view?.citation?.citation_id ?? null;
  useEffect(() => {
    onCitationSelected?.(selectedCitationId);
  }, [selectedCitationId, onCitationSelected]);
  const thread = runs.length ? runs : run ? [run] : [];
  const anchor = useAutoScroll(thread);
  if (!thread.length) return <EmptyWorkspace skills={skills} />;
  return (
    <main id="main-workspace" className="workspace thread" aria-live="polite">
      {thread.map((item, index) => (
        <Turn key={item.id} run={item} view={view} setView={setView}
          first={index === 0} last={index === thread.length - 1}
          onAsk={onAsk} />
      ))}
      <div ref={anchor} aria-hidden="true" />
    </main>
  );
}

/**
 * Keeps the newest turn in view as it arrives.
 *
 * Scrolling on every poll would fight a user reading an earlier answer, so
 * this reacts to the turn count and the latest turn's status only — progress
 * ticks within one turn do not move the page.
 */
function useAutoScroll(thread: SummaryRun[]) {
  const anchor = useRef<HTMLDivElement>(null);
  const status = thread.at(-1)?.status;
  const count = thread.length;
  useEffect(() => {
    if (!count) return;
    anchor.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [count, status]);
  return anchor;
}
