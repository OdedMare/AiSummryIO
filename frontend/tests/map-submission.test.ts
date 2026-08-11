import assert from "node:assert/strict";
import test from "node:test";

import { detectIdentifier } from "../src/components/AppShell/commands";
import { api } from "../src/services/api";
import { toMultiPolygonParts } from "../src/types/geo";

const parts = [
  {
    type: "Polygon" as const,
    coordinates: [[
      [34.75, 32.05], [34.8, 32.05],
      [34.8, 32.1], [34.75, 32.05],
    ]] as [number, number][][],
  },
  {
    type: "Polygon" as const,
    coordinates: [[
      [35.1, 31.9], [35.2, 31.9],
      [35.2, 32], [35.1, 31.9],
    ]] as [number, number][][],
  },
];

test("a drawn area is enough scope without a separate identifier", () => {
  assert.equal(detectIdentifier("", "", null, true), null);
  assert.equal(
    detectIdentifier("", "מזהה: ROOT-1", null, true),
    "ROOT-1",
  );
});

test("map submission sends every drawn part as one MultiPolygon", async (t) => {
  const originalFetch = globalThis.fetch;
  let sentPath: string | URL | Request | undefined;
  let sentOptions: RequestInit | undefined;
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async (path, options) => {
    sentPath = path;
    sentOptions = options;
    return new Response(JSON.stringify({ conversation: {}, run: {} }), {
      status: 202,
      headers: { "Content-Type": "application/json" },
    });
  };

  await api.start("", "", [], toMultiPolygonParts(parts));

  assert.equal(sentPath, "/api/summaries");
  assert.equal(sentOptions?.method, "POST");
  assert.deepEqual(JSON.parse(String(sentOptions?.body)), {
    root_id: null,
    question: "",
    skill_keys: [],
    boundaries: {
      type: "MultiPolygon",
      coordinates: parts.map((part) => part.coordinates),
    },
  });
});
