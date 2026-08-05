import {
  MarkerType,
  type Edge,
  type Node,
  type XYPosition,
} from "reactflow";
import type { PackageVersion, WorkflowStep } from "@/types";
import {
  ANY_FIELD_HANDLE,
  AREA_SOURCE,
  edgeId,
  isSourceNode,
  mappedStep,
  ROOT_SOURCE,
  stepLevels,
  VALUE_SOURCE,
} from "./workflowGraph";

export type OutputField = {
  name: string;
  type: string;
  consumed: boolean;
};

export type StepNodeData = {
  name: string;
  packageName: string;
  inputName: string;
  packageChosen: boolean;
  outputFields: OutputField[];
  selected: boolean;
  incomplete: boolean;
  incompleteReason: string;
};

export type NodeSize = { width: number; height: number };

export const FIT_VIEW_OPTIONS = { padding: 0.18, maxZoom: 1 };

const SOURCE_NODES = [
  { id: ROOT_SOURCE, label: "המזהה הראשי", hint: "מחרוזת מזהה" },
  { id: AREA_SOURCE, label: "האזור מהמפה", hint: "MULTIPOLYGON" },
  { id: VALUE_SOURCE, label: "ערך קבוע", hint: "נשמר עם השלב" },
];

export function minimapNodeColor(node: Node) {
  if (isSourceNode(node.id)) return "var(--border-strong)";
  return (node.data as StepNodeData)?.incomplete
    ? "var(--warning)"
    : "var(--primary)";
}

export function mergeMeasurements(
  derived: Node[],
  sizes: Record<string, NodeSize>,
): Node[] {
  return derived.map((node) => {
    const size = sizes[node.id];
    return size ? { ...node, ...size } : node;
  });
}

export function canvasNodes(
  steps: WorkflowStep[],
  packages: PackageVersion[],
  selectedKey: string,
  moved: Record<string, XYPosition> = {},
): Node[] {
  const sources: Node[] = SOURCE_NODES.map((item, index) => ({
    id: item.id,
    type: "sourceNode",
    position: moved[item.id] ?? { x: 0, y: index * 96 },
    data: item,
    draggable: true,
    deletable: false,
  }));
  const stepNodes: Node[] = [];
  stepLevels(steps).forEach((level, column) => {
    let offset = 0;
    level.forEach((step) => {
      const data = stepNodeData(step, steps, packages, selectedKey);
      stepNodes.push({
        id: step.key,
        type: "stepNode",
        position: moved[step.key] ?? { x: 290 * (column + 1), y: offset },
        data,
        draggable: true,
        deletable: true,
      });
      offset += nodeHeight(data) + 26;
    });
  });
  return [...sources, ...stepNodes];
}

function nodeHeight(data: StepNodeData): number {
  const body = data.outputFields.length
    ? data.outputFields.length * 19 + 8
    : 26;
  return 78 + body + (data.incompleteReason ? 22 : 0);
}

function stepNodeData(
  step: WorkflowStep,
  steps: WorkflowStep[],
  packages: PackageVersion[],
  selectedKey: string,
): StepNodeData {
  const item = packages.find(
    (candidate) => candidate.id === step.package_version_id,
  );
  const consumed = consumedFields(step.key, steps);
  const fields = outputFields(item).map((field) => ({
    ...field,
    consumed: consumed.has(field.name),
  }));
  const reason = incompleteReason(step);
  return {
    name: step.name || step.key,
    packageName: item ? `${item.name} · v${item.version}` : "לא נבחר טול",
    inputName: item?.input_cube_parameter || "input",
    packageChosen: Boolean(item),
    outputFields: fields,
    selected: step.key === selectedKey,
    incomplete: Boolean(reason),
    incompleteReason: reason,
  };
}

function incompleteReason(step: WorkflowStep): string {
  if (!step.package_version_id) return "לא נבחר טול";
  if (step.input_source === VALUE_SOURCE && !step.input_value?.trim()) {
    return "לא הוזן ערך קלט שמור";
  }
  if (mappedStep(step) && !step.input_field.trim()) return "לא נבחר שדה מזהה";
  return "";
}

function consumedFields(key: string, steps: WorkflowStep[]): Set<string> {
  return new Set(steps
    .filter((step) => step.input_source === `steps.${key}`)
    .map((step) => step.input_field.trim())
    .filter(Boolean));
}

function outputFields(item?: PackageVersion): OutputField[] {
  if (!item) return [];
  const schema = item.output_schema as {
    properties?: Record<string, { type?: unknown }>;
  };
  const types = new Map<string, string>();
  Object.entries(schema?.properties ?? {}).forEach(([name, definition]) =>
    types.set(name, fieldType(definition)));
  for (const row of item.example_output ?? []) {
    if (row && typeof row === "object") {
      Object.keys(row).forEach((name) => {
        if (!types.has(name)) types.set(name, "");
      });
    }
  }
  return [...types.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([name, type]) => ({ name, type, consumed: false }));
}

function fieldType(definition: { type?: unknown }): string {
  const type = definition && typeof definition === "object"
    ? definition.type
    : undefined;
  if (Array.isArray(type)) return type.filter(Boolean).join(" | ");
  return typeof type === "string" ? type : "";
}

export function canvasEdges(
  steps: WorkflowStep[],
  packages: PackageVersion[],
): Edge[] {
  return steps.map((step) => {
    const source = step.input_source || ROOT_SOURCE;
    const from = source.startsWith("steps.") ? source.split(".")[1] : source;
    return {
      id: edgeId(from, step.key),
      source: from,
      target: step.key,
      sourceHandle: sourceHandleFor(step, from, steps, packages),
      label: mappedStep(step) && !step.input_field.trim() ? "?" : "",
      markerEnd: { type: MarkerType.ArrowClosed },
      animated: mappedStep(step),
      updatable: true,
      className: mappedStep(step) ? undefined : "is-implicit",
    };
  });
}

function sourceHandleFor(
  step: WorkflowStep,
  from: string,
  steps: WorkflowStep[],
  packages: PackageVersion[],
): string | null {
  if (isSourceNode(from)) return null;
  const field = step.input_field.trim();
  const source = steps.find((candidate) => candidate.key === from);
  const item = packages.find(
    (candidate) => candidate.id === source?.package_version_id,
  );
  const fields = outputFields(item);
  if (!fields.length) return ANY_FIELD_HANDLE;
  return fields.some((candidate) => candidate.name === field) ? field : null;
}
