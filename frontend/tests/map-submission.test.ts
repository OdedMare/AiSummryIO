import assert from "node:assert/strict";
import test from "node:test";

import {
  detectIdentifier, identifierLabel,
} from "../src/components/AppShell/commands";
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
  // `root_id` stays null on the wire: the backend derives it from these same
  // boundaries, so the WKT has one serializer rather than one per side.
  assert.deepEqual(JSON.parse(String(sentOptions?.body)), {
    root_id: null,
    project_id: null,
    question: "",
    skill_keys: [],
    agent_keys: [],
    boundaries: {
      type: "MultiPolygon",
      coordinates: parts.map((part) => part.coordinates),
    },
  });
});


test("manual agents are sent to summaries and evaluations", async (t) => {
  const originalFetch = globalThis.fetch;
  const bodies: Record<string, unknown>[] = [];
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async (_path, options) => {
    bodies.push(JSON.parse(String(options?.body)));
    return new Response("{}", {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  await api.start(
    "ROOT-1", "סכם", [], null, ["geo", "web", "risk"], "project-1",
  );
  await api.createEvaluation({
    project_id: "project-1",
    label: "agents", root_ids: ["ROOT-1"], question: "סכם",
    skill_keys: [], agent_keys: ["geo", "web", "risk"],
    cooldown_seconds: 0,
  });

  assert.deepEqual(bodies.map((body) => body.agent_keys), [
    ["geo", "web", "risk"], ["geo", "web", "risk"],
  ]);
  assert.deepEqual(bodies.map((body) => body.project_id), [
    "project-1", "project-1",
  ]);
});


test("a project keeps the mission and exact capability keys", async (t) => {
  const originalFetch = globalThis.fetch;
  let sentPath = "";
  let sentBody: Record<string, unknown> = {};
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async (path, options) => {
    sentPath = String(path);
    sentBody = JSON.parse(String(options?.body));
    return new Response(JSON.stringify({ id: "project-1", ...sentBody }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  await api.createProject({
    name: "בדיקת חריגים",
    mission: "להסביר עסקאות חריגות רק מראיות זמינות",
    tool_keys: ["transactions"],
    workflow_keys: ["risk-review"],
    skill_keys: ["red-flags"],
    agent_keys: ["risk-agent"],
  });

  assert.equal(sentPath, "/api/projects");
  assert.deepEqual(sentBody, {
    name: "בדיקת חריגים",
    mission: "להסביר עסקאות חריגות רק מראיות זמינות",
    tool_keys: ["transactions"],
    workflow_keys: ["risk-review"],
    skill_keys: ["red-flags"],
    agent_keys: ["risk-agent"],
  });
});


test("a multipolygon identifier is clipped where it is only a label", () => {
  const wkt = "MULTIPOLYGON (((34.75 32.05, 34.8 32.05, 34.8 32.1, "
    + "34.75 32.05)), ((35.1 31.9, 35.2 31.9, 35.2 32, 35.1 31.9)))";

  assert.equal(identifierLabel(wkt), "MULTIPOLYGON (((34.75 32.05, 34…");
  assert.equal(identifierLabel(wkt).length, 32);
  assert.equal(identifierLabel("HOME-ABC-001"), "HOME-ABC-001");
});


test("multipolygon identifiers are sent unchanged in live, inspect, and dry run", async (t) => {
  const originalFetch = globalThis.fetch;
  const requests: Array<{ path: string; body: Record<string, unknown> }> = [];
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async (path, options) => {
    requests.push({
      path: String(path),
      body: JSON.parse(String(options?.body)),
    });
    return new Response("{}", {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const identifier = "MULTIPOLYGON (((" + Array.from(
    { length: 40 },
    (_, index) => `34.${String(index).padStart(7, "0")} 32.${String(index).padStart(7, "0")}`,
  ).concat("34.0000000 32.0000000").join(", ") + ")))";

  await api.start(identifier, "", []);
  await api.inspectPackage({ root_id: identifier });
  await api.dryRun("workflow-geo", identifier);

  assert.ok(identifier.length > 256);
  assert.equal(requests[0].body.root_id, identifier);
  assert.equal(requests[1].body.root_id, identifier);
  assert.equal(requests[2].body.root_id, identifier);
  assert.equal(requests[2].path, "/api/workflows/workflow-geo/dry-run");
});
