"use client";

import type { Citation, SummaryClaim } from "@/types";
import {
  citedSegments, citationNumbers, lineCitations,
} from "./citations";

/**
 * Inline citation markers beside the text they support.
 *
 * A marker is a number, rendered next to the claim rather than collected at
 * the end, because "which source says this" is a question about one sentence.
 * Clicking opens that exact record in the evidence drawer the thread already
 * has — a citation is a route into the existing evidence UI, never a second
 * one beside it.
 */
export function CitationChip({
  citation, number, active, onSelect,
}: {
  citation: Citation;
  number: number;
  active: boolean;
  onSelect: (citation: Citation) => void;
}) {
  return (
    <button
      type="button"
      className={`citation-chip ${active ? "active" : ""}`}
      aria-pressed={active}
      /* The number alone is meaningless to a screen reader, so the accessible
         name says what it opens and which source it points at. */
      aria-label={`מקור ${number}: ${citation.label}. הצגת הרשומה`}
      title={citation.excerpt || citation.label}
      onClick={() => onSelect(citation)}
    >
      [{number}]
    </button>
  );
}

/** The markers for one set of citations, in catalog order. */
export function CitationMarkers({
  citations, numbers, activeId, onSelect,
}: {
  citations: Citation[];
  numbers: Map<string, number>;
  activeId: string | null;
  onSelect: (citation: Citation) => void;
}) {
  if (!citations.length) return null;
  return (
    <span className="citation-markers">
      {citations.map((citation) => (
        <CitationChip
          key={citation.citation_id}
          citation={citation}
          number={numbers.get(citation.citation_id) ?? 0}
          active={activeId === citation.citation_id}
          onSelect={onSelect}
        />
      ))}
    </span>
  );
}

/**
 * Prose with a marker after each sentence that was traced to a source.
 *
 * Falls back to the text unchanged when there are no claims, which is what an
 * answer produced before citations existed always renders as.
 */
export function CitedText({
  text, claims, citations, activeId, onSelect,
}: {
  text: string;
  claims: SummaryClaim[];
  citations: Citation[];
  activeId: string | null;
  onSelect: (citation: Citation) => void;
}) {
  const numbers = citationNumbers(citations);
  const segments = citedSegments(text, claims, citations);
  if (!segments.length) return null;
  return (
    <>
      {segments.map((segment, index) => (
        <span key={index}>
          {segment.text}
          <CitationMarkers citations={segment.citations} numbers={numbers}
            activeId={activeId} onSelect={onSelect} />
        </span>
      ))}
    </>
  );
}

/** One standalone line — a finding or a risk — with its markers after it. */
export function CitedLine({
  line, claims, citations, activeId, onSelect,
}: {
  line: string;
  claims: SummaryClaim[];
  citations: Citation[];
  activeId: string | null;
  onSelect: (citation: Citation) => void;
}) {
  const cited = lineCitations(line, claims, citations);
  return (
    <>
      {line}
      <CitationMarkers citations={cited} numbers={citationNumbers(citations)}
        activeId={activeId} onSelect={onSelect} />
    </>
  );
}
