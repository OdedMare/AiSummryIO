import type {
  PackageVersion, WorkflowStep, WorkflowVersion,
} from "@/types";
import { emptyWorkflow, parseJson } from "../forms";
import { orderedSteps } from "./workflowGraph";

export function workflowForm(item: WorkflowVersion) {
  return {
    workflow_key: item.workflow_key,
    name: item.name,
    description: item.description,
    role: item.role,
    agent_enabled: item.agent_enabled,
    system_prompt: item.system_prompt,
    output_schema: JSON.stringify(item.output_schema, null, 2),
    examples: JSON.stringify(item.examples, null, 2),
  };
}

/** Build the section extension used by a one-tool workflow. */
export function toolOutputSchema(
  item: PackageVersion,
): Record<string, unknown> {
  const declared = item.output_schema as {
    properties?: Record<string, unknown>;
  } | null;
  const properties = declared?.properties
    && typeof declared.properties === "object"
    ? declared.properties
    : inferredProperties(item.example_output ?? []);
  return {
    type: "object",
    properties: {
      rows: {
        type: "array",
        description: `שורות הפלט של ${item.name}`,
        items: Object.keys(properties).length
          ? { type: "object", properties }
          : { type: "object" },
      },
    },
  };
}

function inferredProperties(
  examples: Array<Record<string, unknown>>,
): Record<string, unknown> {
  const row = examples.find(
    (candidate) => candidate && typeof candidate === "object",
  );
  if (!row) return {};
  return Object.fromEntries(Object.entries(row).map(
    ([name, value]) => [name, { type: jsonType(value) }],
  ));
}

function jsonType(value: unknown): string {
  if (typeof value === "number") return "number";
  if (typeof value === "boolean") return "boolean";
  if (Array.isArray(value)) return "array";
  if (value && typeof value === "object") return "object";
  return "string";
}

export function workflowPayload(
  form: typeof emptyWorkflow,
  steps: WorkflowStep[],
) {
  return {
    ...form,
    workflow_key: form.workflow_key || undefined,
    output_schema: parseJson<Record<string, unknown>>(form.output_schema, {}),
    examples: parseJson<Array<Record<string, unknown>>>(form.examples, []),
    // The backend resolves a source only from steps already visited.
    steps: orderedSteps(steps),
  };
}

export function releaseDependents(
  steps: WorkflowStep[],
  removedKey: string,
) {
  if (!removedKey) return steps;
  return steps.map((step) => step.input_source === `steps.${removedKey}`
    ? patchedStep(step, { input_source: "workflow.id", input_field: "" })
    : step);
}

export function newStep(
  steps: WorkflowStep[],
  packages: PackageVersion[],
): WorkflowStep {
  const index = steps.length + 1;
  return {
    key: `step-${index}`,
    name: `שלב ${index}`,
    package_version_id: packages[0]?.id ?? "",
    depends_on: [],
    input_source: "workflow.id",
    input_field: "",
    input_value: "",
    summary_prompt: "",
  };
}

export function patchedStep(
  step: WorkflowStep,
  patch: Partial<WorkflowStep>,
) {
  const next = { ...step, ...patch };
  next.depends_on = next.input_source.startsWith("steps.")
    ? [next.input_source.split(".")[1]]
    : [];
  if (!next.input_source.startsWith("steps.")) next.input_field = "";
  if (next.input_source !== "workflow.value") next.input_value = "";
  return next;
}

export function sourceOutputFields(
  step: WorkflowStep,
  index: number,
  steps: WorkflowStep[],
  packages: PackageVersion[],
) {
  const sourceKey = step.input_source.startsWith("steps.")
    ? step.input_source.split(".")[1]
    : "";
  if (!sourceKey) return [];
  const source = steps.slice(0, index).find((prior) => prior.key === sourceKey);
  const item = packages.find(
    (candidate) => candidate.id === source?.package_version_id,
  );
  return item ? outputFields(item) : [];
}

/** Keep the picker aligned with the backend's output-field discovery. */
function outputFields(item: PackageVersion) {
  const schema = item.output_schema as {
    properties?: Record<string, unknown>;
  };
  const properties = schema?.properties;
  const names = new Set<string>(
    properties && typeof properties === "object"
      ? Object.keys(properties)
      : [],
  );
  for (const row of item.example_output ?? []) {
    if (row && typeof row === "object") {
      Object.keys(row).forEach((field) => names.add(field));
    }
  }
  return [...names].sort();
}

export function errorMessage(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback;
}
