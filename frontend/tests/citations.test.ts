import assert from "node:assert/strict";
import test from "node:test";

import {
  citationNumbers, citedSegments, hasCitations, lineCitations,
  trailingCitations,
} from "../src/components/SummaryWorkspace/citations";
import { api } from "../src/services/api";
import type { Citation, SummaryResult } from "../src/types";

const ownership: Citation = {
  citation_id: "c1",
  evidence_id: "ev-1",
  source_id: "ev-1",
  workflow_id: "wf-1",
  workflow_key: "ownership",
  step_key: "owners",
  label: "בעלות",
  fields: ["owner", "house"],
  excerpt: "owner: דנה · house: הבית האדום",
  row_count: 1,
};

const deals: Citation = {
  ...ownership,
  citation_id: "c2",
  evidence_id: "ev-2",
  source_id: "ev-2",
  label: "עסקאות",
  step_key: "deals",
};

function result(overrides: Partial<SummaryResult> = {}): SummaryResult {
  return {
    summary: "",
    key_findings: [],
    risks: [],
    missing_data: [],
    suggested_questions: [],
    skill_results: [],
    sections: [],
    partial: false,
    ...overrides,
  };
}

test("a claim's sentence carries the marker for the source behind it", () => {
  const text = "דנה היא הבעלים. הבית נמכר ב-2019.";
  const segments = citedSegments(
    text,
    [{ text: "דנה היא הבעלים.", citation_ids: ["c1"] }],
    [ownership],
  );

  assert.equal(segments.map((part) => part.text).join(""), text);
  const cited = segments.filter((part) => part.citations.length);
  assert.equal(cited.length, 1);
  assert.equal(cited[0].text, "דנה היא הבעלים.");
  assert.deepEqual(cited[0].citations.map((item) => item.citation_id), ["c1"]);
});

test("a marker keeps one number per source across the whole answer", () => {
  const numbers = citationNumbers([ownership, deals, ownership]);

  assert.equal(numbers.get("c1"), 1);
  assert.equal(numbers.get("c2"), 2);
});

test("a citation id with no matching source renders no marker", () => {
  // The backend already drops unknown ids; the UI must not render a number
  // pointing at nothing if one ever arrives.
  const segments = citedSegments(
    "טענה כלשהי.",
    [{ text: "טענה כלשהי.", citation_ids: ["c99"] }],
    [ownership],
  );

  assert.deepEqual(segments, [{ text: "טענה כלשהי.", citations: [] }]);
});

test("a summary with no citation metadata renders as plain text", () => {
  // Every summary produced before citations existed takes this path.
  assert.deepEqual(
    citedSegments("סיכום ישן.", [], []),
    [{ text: "סיכום ישן.", citations: [] }],
  );
  assert.equal(hasCitations(result({ summary: "סיכום ישן." })), false);
  assert.equal(hasCitations(null), false);
  assert.deepEqual(trailingCitations(result({ summary: "ישן" })), []);
});

test("a finding carries the markers of the claim that states it", () => {
  const cited = lineCitations(
    "דנה היא הבעלים",
    [{ text: "דנה היא הבעלים", citation_ids: ["c1", "c2"] }],
    [ownership, deals],
  );

  assert.deepEqual(cited.map((item) => item.citation_id), ["c1", "c2"]);
  // A line no claim states carries none.
  assert.deepEqual(lineCitations("שורה אחרת", [], [ownership]), []);
});

test("a traced claim that never appears verbatim keeps its source reachable", () => {
  // The claim was traced but the model reworded the prose, so the marker has
  // nowhere inline to sit. Losing it would break the evidence rule.
  const trailing = trailingCitations(result({
    summary: "הבעלות נבדקה.",
    claims: [{ text: "דנה היא הבעלים", citation_ids: ["c1"] }],
    citations: [ownership],
  }));

  assert.deepEqual(trailing.map((item) => item.citation_id), ["c1"]);
});

test("a claim shown inline is not repeated as a trailing source", () => {
  const trailing = trailingCitations(result({
    summary: "דנה היא הבעלים",
    claims: [{ text: "דנה היא הבעלים", citation_ids: ["c1"] }],
    citations: [ownership],
  }));

  assert.deepEqual(trailing, []);
});

test("overlapping claims never split each other's sentence", () => {
  const segments = citedSegments(
    "דנה היא הבעלים של הבית האדום.",
    [
      { text: "דנה היא הבעלים של הבית האדום.", citation_ids: ["c1"] },
      { text: "הבעלים", citation_ids: ["c2"] },
    ],
    [ownership, deals],
  );

  // The longer claim wins; the contained one is not allowed to cut it.
  assert.equal(segments.length, 1);
  assert.deepEqual(
    segments[0].citations.map((item) => item.citation_id), ["c1"],
  );
});

test("a follow-up asked with a citation selected sends its id", async (t) => {
  const originalFetch = globalThis.fetch;
  let sentOptions: RequestInit | undefined;
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async (_path, options) => {
    sentOptions = options;
    return new Response(JSON.stringify({}), {
      status: 202,
      headers: { "Content-Type": "application/json" },
    });
  };

  await api.followUp("conv-1", "הצג לי את הרשומה הזו", [], [], "c1");

  assert.deepEqual(JSON.parse(String(sentOptions?.body)), {
    question: "הצג לי את הרשומה הזו",
    skill_keys: [],
    agent_keys: [],
    citation_id: "c1",
    referenced_citation_ids: [],
  });
});

test("a follow-up asked with nothing selected sends a null citation", async (t) => {
  const originalFetch = globalThis.fetch;
  let sentOptions: RequestInit | undefined;
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async (_path, options) => {
    sentOptions = options;
    return new Response(JSON.stringify({}), {
      status: 202,
      headers: { "Content-Type": "application/json" },
    });
  };

  await api.followUp("conv-1", "ולמה?", []);

  const body = JSON.parse(String(sentOptions?.body));
  assert.equal(body.citation_id, null);
  assert.deepEqual(body.referenced_citation_ids, []);
});

test("resolving a citation is scoped to the conversation that owns it", async (t) => {
  const originalFetch = globalThis.fetch;
  let sentPath: string | URL | Request | undefined;
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async (path) => {
    sentPath = path;
    return new Response(JSON.stringify({ citation: {}, record: {} }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  await api.resolveCitation("conv-1", "c1");

  // Scoped by conversation, so the same ownership check the evidence routes
  // apply guards this one too.
  assert.equal(sentPath, "/api/conversations/conv-1/citations/c1?limit=20");
});
