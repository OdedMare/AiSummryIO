import type { Citation, SummaryClaim, SummaryResult } from "@/types";

/**
 * Turning an answer's `claims` into text with inline citation markers.
 *
 * The backend returns the answer prose and, separately, the claims it traced
 * to sources. Rendering is therefore a matching problem: find each claim's
 * sentence inside the text it came from and attach that claim's markers to it.
 * It is kept here, as pure functions over data, because that is what makes it
 * testable without a DOM — the components below only map the result to JSX.
 *
 * Everything degrades to plain text. A summary from before citations existed
 * has no `claims`, an unmatched claim contributes no marker, and a marker
 * whose citation is missing from `citations` is dropped rather than rendered
 * as a number pointing at nothing.
 */

/** One run of text, with the citations that support it. */
export interface CitedSegment {
  text: string;
  citations: Citation[];
}

/** Numbering is per answer and follows `citations` order, so the same source
    keeps one number wherever it is cited in that answer. */
export function citationNumbers(citations: Citation[]): Map<string, number> {
  const numbers = new Map<string, number>();
  citations.forEach((citation, index) => {
    if (!numbers.has(citation.citation_id)) {
      numbers.set(citation.citation_id, index + 1);
    }
  });
  return numbers;
}

export function citationsById(citations: Citation[]): Map<string, Citation> {
  return new Map(citations.map((item) => [item.citation_id, item]));
}

/** The citations one claim resolves to, dropping ids with no citation. */
export function claimCitations(
  claim: SummaryClaim,
  byId: Map<string, Citation>,
): Citation[] {
  return claim.citation_ids
    .map((id) => byId.get(id))
    .filter((item): item is Citation => Boolean(item));
}

/**
 * Split `text` into segments, attaching each claim's citations to the part of
 * the text that claim states.
 *
 * A claim's `text` is the sentence as the model wrote it in the answer, so an
 * exact substring match is the reliable signal — a fuzzy match would attach a
 * source to a sentence it does not support, which is worse than no marker at
 * all. Claims that do not appear verbatim are left for `trailingCitations`.
 */
export function citedSegments(
  text: string,
  claims: SummaryClaim[],
  citations: Citation[],
): CitedSegment[] {
  if (!text) return [];
  const byId = citationsById(citations);
  const spans = matchedSpans(text, claims, byId);
  if (!spans.length) return [{ text, citations: [] }];

  const segments: CitedSegment[] = [];
  let cursor = 0;
  for (const span of spans) {
    if (span.start > cursor) {
      segments.push({ text: text.slice(cursor, span.start), citations: [] });
    }
    segments.push({
      text: text.slice(span.start, span.end),
      citations: span.citations,
    });
    cursor = span.end;
  }
  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), citations: [] });
  }
  return segments;
}

interface Span {
  start: number;
  end: number;
  citations: Citation[];
}

/** Non-overlapping spans, longest claim first so a claim contained inside a
    longer one does not split it. */
function matchedSpans(
  text: string,
  claims: SummaryClaim[],
  byId: Map<string, Citation>,
): Span[] {
  const found: Span[] = [];
  const ordered = [...claims].sort((a, b) => b.text.length - a.text.length);
  for (const claim of ordered) {
    const cited = claimCitations(claim, byId);
    if (!cited.length || !claim.text.trim()) continue;
    const start = text.indexOf(claim.text);
    if (start < 0) continue;
    const end = start + claim.text.length;
    if (found.some((span) => start < span.end && end > span.start)) continue;
    found.push({ start, end, citations: cited });
  }
  return found.sort((a, b) => a.start - b.start);
}

/**
 * Citations for a standalone line such as a finding or a risk.
 *
 * These are rendered as whole items rather than as prose, so a marker belongs
 * after the line rather than inside it. An exact claim match is preferred;
 * without one the line carries no marker.
 */
export function lineCitations(
  line: string,
  claims: SummaryClaim[],
  citations: Citation[],
): Citation[] {
  const byId = citationsById(citations);
  const claim = claims.find((item) => item.text === line);
  return claim ? claimCitations(claim, byId) : [];
}

/**
 * Citations that were traced but never matched to visible text.
 *
 * Without this a claim whose sentence the model reworded would silently lose
 * its source. Showing it at the end of the answer keeps every traced claim
 * reachable, which is the rule that claims require evidence references.
 */
export function trailingCitations(result: SummaryResult): Citation[] {
  const claims = result.claims ?? [];
  const citations = result.citations ?? [];
  if (!claims.length || !citations.length) return [];
  const byId = citationsById(citations);
  const shown = new Set<string>();
  const bodies = [result.summary ?? "", ...(result.key_findings ?? []),
    ...(result.risks ?? [])];
  for (const claim of claims) {
    const inText = bodies.some((body) => body.includes(claim.text));
    if (!inText) continue;
    for (const item of claimCitations(claim, byId)) {
      shown.add(item.citation_id);
    }
  }
  const cited = new Set(
    claims.flatMap((claim) => claim.citation_ids).filter((id) => byId.has(id)),
  );
  return [...cited]
    .filter((id) => !shown.has(id))
    .map((id) => byId.get(id))
    .filter((item): item is Citation => Boolean(item));
}

/** Whether an answer carries anything citable. Old summaries return false and
    the UI renders exactly as it did before citations existed. */
export function hasCitations(result: SummaryResult | null): boolean {
  return Boolean(result?.citations?.length && result?.claims?.length);
}
