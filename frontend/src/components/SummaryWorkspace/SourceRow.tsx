"use client";

import { AlertTriangle } from "lucide-react";
import type { SummarySection } from "@/types";

/** The section model survives as provenance rather than as layout: the prose
    above merges every workflow, so this row is the only place a reader can see
    which ones it rests on. A chip opens that workflow's whole evidence.

    Per-claim citation markers now sit inline in the answer above
    (`CitationChip`), and open one record rather than a workflow's whole set.
    Both routes filter the same drawer, so this row stays the way to ask "what
    did this source contribute" as a whole. */
export default function SourceRow({
  sections, activeId, onSelect,
}: {
  sections: SummarySection[];
  activeId: string | null;
  onSelect: (section: SummarySection) => void;
}) {
  if (!sections.length) return null;
  return (
    <section className="source-row" aria-labelledby="source-row-title">
      <h2 id="source-row-title">מקורות</h2>
      <ul>
        {sections.map((section) => (
          <li key={section.workflow_id}>
            <SourceChip section={section} active={activeId === section.workflow_id}
              onSelect={onSelect} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function SourceChip({
  section, active, onSelect,
}: {
  section: SummarySection;
  active: boolean;
  onSelect: (section: SummarySection) => void;
}) {
  const complete = section.status === "completed";
  const label = complete ? "הושלם"
    : section.status === "partial" ? "כיסוי חלקי" : "נכשל";
  return (
    <button type="button" className={`source-chip ${active ? "active" : ""}`}
      aria-pressed={active} onClick={() => onSelect(section)}>
      <span className={`source-dot ${section.status}`} aria-hidden="true" />
      <span className="source-name">{section.name}</span>
      {!complete && <AlertTriangle size={13} aria-hidden="true" />}
      <small>{label}</small>
    </button>
  );
}
