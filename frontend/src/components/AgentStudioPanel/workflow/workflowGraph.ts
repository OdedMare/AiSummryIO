import type { WorkflowStep } from "@/types";

export const ROOT_SOURCE = "workflow.id";
export const AREA_SOURCE = "workflow.boundaries";
export const VALUE_SOURCE = "workflow.value";

const SOURCE_IDS = new Set([ROOT_SOURCE, AREA_SOURCE, VALUE_SOURCE]);
const EDGE_SEPARATOR = "~>";
export const ANY_FIELD_HANDLE = "*";

export function connectedField(handle: string | null | undefined): string {
  return !handle || handle === ANY_FIELD_HANDLE ? "" : handle;
}

export function sourceExpression(nodeId: string) {
  return isSourceNode(nodeId) ? nodeId : `steps.${nodeId}`;
}

export function isSourceNode(nodeId: string) {
  return SOURCE_IDS.has(nodeId);
}

export function edgeId(from: string, to: string) {
  return `${from}${EDGE_SEPARATOR}${to}`;
}

export function targetOfEdge(id: string) {
  return id.split(EDGE_SEPARATOR)[1] ?? "";
}

export function createsCycle(
  steps: WorkflowStep[],
  source: string,
  target: string,
): boolean {
  if (isSourceNode(source)) return false;
  const byKey = new Map(steps.map((step) => [step.key, step]));
  let current: string | undefined = source;
  const visited = new Set<string>();
  while (current && !visited.has(current)) {
    if (current === target) return true;
    visited.add(current);
    const step: WorkflowStep | undefined = byKey.get(current);
    const next: string = step?.input_source ?? "";
    current = next.startsWith("steps.") ? next.split(".")[1] : undefined;
  }
  return false;
}

/** Mirrors the backend: independent steps share one execution level. */
export function stepLevels(steps: WorkflowStep[]) {
  const levels: WorkflowStep[][] = [];
  const placed = new Set<string>();
  let remaining = [...steps];
  while (remaining.length) {
    const level = remaining.filter((step) =>
      dependencies(step).every((key) => placed.has(key)));
    if (!level.length) {
      levels.push(remaining);
      break;
    }
    level.forEach((step) => placed.add(step.key));
    levels.push(level);
    remaining = remaining.filter((step) => !level.includes(step));
  }
  return levels;
}

function dependencies(step: WorkflowStep) {
  const declared = new Set(step.depends_on ?? []);
  const parts = (step.input_source || ROOT_SOURCE).split(".");
  if (parts.length >= 2 && parts[0] === "steps") declared.add(parts[1]);
  return [...declared];
}

export function orderedSteps(steps: WorkflowStep[]): WorkflowStep[] {
  return stepLevels(steps).flat();
}

export function mappedStep(step: WorkflowStep) {
  return !SOURCE_IDS.has(step.input_source);
}
