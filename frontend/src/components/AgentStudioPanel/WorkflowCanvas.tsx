"use client";

/**
 * Drag-to-connect authoring surface for a workflow's steps.
 *
 * The canvas is a view over the same `WorkflowStep[]` the step cards edit —
 * it owns no step state of its own. Dragging an edge writes `input_source`
 * and `depends_on`; deleting one resets the target back to the main
 * identifier. That keeps every graph the canvas can draw inside what
 * `Repository._validate_steps` accepts, so a workflow wired here can always
 * be saved.
 */

import { useCallback, useMemo } from "react";
import ReactFlow, {
  Background, Controls, Handle, MarkerType, Position,
  type Connection, type Edge, type EdgeChange, type Node, type NodeProps,
} from "reactflow";
import "reactflow/dist/style.css";
import { Map as MapIcon, Package, Tag } from "lucide-react";
import type { PackageVersion, WorkflowStep } from "@/types";

/** The two workflow-level inputs, drawn as fixed source nodes. */
const ROOT_SOURCE = "workflow.id";
const AREA_SOURCE = "workflow.boundaries";

const SOURCE_NODES = [
  { id: ROOT_SOURCE, label: "המזהה הראשי", hint: "מחרוזת מזהה" },
  { id: AREA_SOURCE, label: "האזור מהמפה", hint: "MULTIPOLYGON" },
];

export default function WorkflowCanvas({
  steps, packages, onConnectStep, onDisconnectStep, onSelectStep, selectedKey,
}: {
  steps: WorkflowStep[];
  packages: PackageVersion[];
  onConnectStep: (targetKey: string, source: string) => void;
  onDisconnectStep: (targetKey: string) => void;
  onSelectStep: (key: string) => void;
  selectedKey: string;
}) {
  const nodes = useMemo(
    () => canvasNodes(steps, packages, selectedKey), [steps, packages, selectedKey]);
  const edges = useMemo(() => canvasEdges(steps), [steps]);

  // A step carries exactly one `input_source`, so a new connection replaces
  // whatever fed that node rather than adding a second incoming edge.
  const onConnect = useCallback((connection: Connection) => {
    if (!connection.source || !connection.target) return;
    if (connection.source === connection.target) return;
    if (createsCycle(steps, connection.source, connection.target)) return;
    onConnectStep(connection.target, sourceExpression(connection.source));
  }, [steps, onConnectStep]);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    changes.forEach((change) => {
      if (change.type === "remove") {
        onDisconnectStep(targetOfEdge(change.id));
      }
    });
  }, [onDisconnectStep]);

  return (
    <div className="workflow-canvas" aria-label="עריכת חיבורי התהליך">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        onConnect={onConnect}
        onEdgesChange={onEdgesChange}
        onNodeClick={(_, node) => {
          if (!isSourceNode(node.id)) onSelectStep(node.id);
        }}
        fitView
        proOptions={{ hideAttribution: true }}
        nodesDraggable
        nodesConnectable
        deleteKeyCode={["Backspace", "Delete"]}
      >
        <Background gap={18} size={1} />
        <Controls showInteractive={false} position="bottom-left" />
      </ReactFlow>
      <p className="canvas-hint">
        גררו מהנקודה שבצד שלב אל שלב אחר כדי להזרים אליו את הפלט.
        בחירת שלב פותחת אותו לעריכה. מחיקת חיבור מחזירה את השלב למזהה הראשי.
      </p>
    </div>
  );
}

/* ---------- nodes ---------- */

function SourceNode({ data }: NodeProps<{ label: string; hint: string }>) {
  return (
    <div className="canvas-node canvas-node-source">
      <span className="canvas-node-icon">
        {data.hint === "MULTIPOLYGON"
          ? <MapIcon size={15} aria-hidden="true" />
          : <Tag size={15} aria-hidden="true" />}
      </span>
      <div>
        <strong>{data.label}</strong>
        <small dir="ltr">{data.hint}</small>
      </div>
      <Handle type="source" position={Position.Left} />
    </div>
  );
}

function StepNode({ data }: NodeProps<StepNodeData>) {
  return (
    <div className={`canvas-node canvas-node-step${
      data.selected ? " is-selected" : ""}${data.incomplete ? " is-incomplete" : ""}`}>
      <Handle type="target" position={Position.Right} />
      <span className="canvas-node-icon">
        <Package size={15} aria-hidden="true" />
      </span>
      <div>
        <strong>{data.name}</strong>
        <small dir="ltr">{data.packageName}</small>
        {data.mapping && <small className="canvas-node-mapping" dir="ltr">
          → {data.mapping}
        </small>}
      </div>
      <Handle type="source" position={Position.Left} />
    </div>
  );
}

type StepNodeData = {
  name: string;
  packageName: string;
  mapping: string;
  selected: boolean;
  incomplete: boolean;
};

const NODE_TYPES = { sourceNode: SourceNode, stepNode: StepNode };

function canvasNodes(
  steps: WorkflowStep[], packages: PackageVersion[], selectedKey: string,
): Node[] {
  const levels = stepLevels(steps);
  const sources: Node[] = SOURCE_NODES.map((item, index) => ({
    id: item.id,
    type: "sourceNode",
    position: { x: 0, y: index * 110 },
    data: item,
    draggable: true,
  }));
  const stepNodes: Node[] = [];
  levels.forEach((level, column) => {
    level.forEach((step, row) => {
      stepNodes.push({
        id: step.key,
        type: "stepNode",
        // RTL reads right-to-left, but React Flow's x axis does not flip, so
        // the layout runs left-to-right and the handles are mirrored instead.
        position: { x: 260 * (column + 1), y: row * 110 },
        data: stepNodeData(step, packages, selectedKey),
        draggable: true,
      });
    });
  });
  return [...sources, ...stepNodes];
}

function stepNodeData(
  step: WorkflowStep, packages: PackageVersion[], selectedKey: string,
): StepNodeData {
  const item = packages.find((candidate) => candidate.id === step.package_version_id);
  return {
    name: step.name || step.key,
    packageName: item ? `${item.name} · v${item.version}` : "לא נבחר טול",
    mapping: mappedStep(step) ? step.input_field : "",
    selected: step.key === selectedKey,
    // A mapped step with no chosen field, or a step with no package, cannot
    // be published — the canvas says so before the FDE reaches the button.
    incomplete: !step.package_version_id ||
      (mappedStep(step) && !step.input_field.trim()),
  };
}

/* ---------- edges ---------- */

function canvasEdges(steps: WorkflowStep[]): Edge[] {
  return steps.map((step) => {
    const source = step.input_source || ROOT_SOURCE;
    const from = source.startsWith("steps.") ? source.split(".")[1] : source;
    return {
      id: edgeId(from, step.key),
      source: from,
      target: step.key,
      label: mappedStep(step) ? step.input_field || "?" : "",
      markerEnd: { type: MarkerType.ArrowClosed },
      animated: mappedStep(step),
    };
  });
}

const EDGE_SEPARATOR = "~>";

function edgeId(from: string, to: string) {
  return `${from}${EDGE_SEPARATOR}${to}`;
}

function targetOfEdge(id: string) {
  return id.split(EDGE_SEPARATOR)[1] ?? "";
}

/** `steps.<key>` for a step source; the workflow-level sources pass through. */
function sourceExpression(nodeId: string) {
  return isSourceNode(nodeId) ? nodeId : `steps.${nodeId}`;
}

function isSourceNode(nodeId: string) {
  return nodeId === ROOT_SOURCE || nodeId === AREA_SOURCE;
}

/**
 * Whether feeding `target` from `source` would close a loop.
 *
 * `_validate_steps` rejects a cycle only at save time, with a message naming
 * keys rather than the connection just drawn. Refusing the drag is the
 * clearer place to say no.
 */
function createsCycle(
  steps: WorkflowStep[], source: string, target: string,
): boolean {
  if (isSourceNode(source)) return false;
  const byKey = new Map(steps.map((step) => [step.key, step]));
  let current: string | undefined = source;
  const visited = new Set<string>();
  while (current && !visited.has(current)) {
    if (current === target) return true;
    visited.add(current);
    const step: WorkflowStep | undefined = byKey.get(current);
    const next = step?.input_source ?? "";
    current = next.startsWith("steps.") ? next.split(".")[1] : undefined;
  }
  return false;
}

/* ---------- layout ---------- */

// Mirrors the backend's step_levels: steps whose dependencies are all
// satisfied by earlier levels share a level and run concurrently.
function stepLevels(steps: WorkflowStep[]) {
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

/**
 * Steps ordered so every step follows the one it reads.
 *
 * `_validate_source` requires the source key to have been *seen* already,
 * which for the stored array means a lower position. On a canvas the FDE can
 * wire a later node backwards into an earlier one, so the array is sorted by
 * dependency level before it is saved.
 */
export function orderedSteps(steps: WorkflowStep[]): WorkflowStep[] {
  return stepLevels(steps).flat();
}

export function mappedStep(step: WorkflowStep) {
  return step.input_source !== ROOT_SOURCE &&
    step.input_source !== AREA_SOURCE;
}
