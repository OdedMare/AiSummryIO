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

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import ReactFlow, {
  Background, Controls, Handle, MarkerType, MiniMap, Position,
  applyNodeChanges,
  type Connection, type Edge, type EdgeChange, type Node, type NodeChange,
  type NodeProps, type XYPosition,
} from "reactflow";
import "reactflow/dist/style.css";
import {
  AlertTriangle, GitCommitHorizontal, Map as MapIcon, Maximize2, Minimize2,
  Package, Rows3, Tag,
} from "lucide-react";
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
  onConnectStep: (
    targetKey: string, source: string, inputField: string,
  ) => void;
  onDisconnectStep: (targetKey: string) => void;
  onSelectStep: (key: string) => void;
  selectedKey: string;
}) {
  const nodes = useMemo(
    () => canvasNodes(steps, packages, selectedKey), [steps, packages, selectedKey]);
  const edges = useMemo(
    () => canvasEdges(steps, packages), [steps, packages]);

  // A step carries exactly one `input_source`, so a new connection replaces
  // whatever fed that node rather than adding a second incoming edge. The
  // source handle names the output field, so one drag sets both halves of
  // the mapping.
  const onConnect = useCallback((connection: Connection) => {
    if (!connection.source || !connection.target) return;
    if (connection.source === connection.target) return;
    if (createsCycle(steps, connection.source, connection.target)) return;
    onConnectStep(
      connection.target,
      sourceExpression(connection.source),
      connectedField(connection.sourceHandle),
    );
  }, [steps, onConnectStep]);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    changes.forEach((change) => {
      if (change.type === "remove") {
        onDisconnectStep(targetOfEdge(change.id));
      }
    });
  }, [onDisconnectStep]);

  /**
   * Dragging an existing edge's endpoint elsewhere — moving a string.
   *
   * React Flow reports this as an update rather than a remove plus a
   * connect, so without it an edge dragged onto another field snapped back.
   */
  const onEdgeUpdate = useCallback((previous: Edge, connection: Connection) => {
    if (!connection.source || !connection.target) return;
    if (connection.source === connection.target) return;
    if (createsCycle(steps, connection.source, connection.target)) return;
    // A moved edge can leave its old target unfed; release it first so the
    // step falls back to the main identifier instead of keeping a mapping
    // nothing points at any more.
    if (previous.target !== connection.target) {
      onDisconnectStep(previous.target);
    }
    onConnectStep(
      connection.target,
      sourceExpression(connection.source),
      connectedField(connection.sourceHandle),
    );
  }, [steps, onConnectStep, onDisconnectStep]);

  const [expanded, setExpanded] = useState(false);
  useEscapeToClose(expanded, () => setExpanded(false));
  useLockedBodyScroll(expanded);

  const graph = (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={NODE_TYPES}
      onConnect={onConnect}
      onEdgeUpdate={onEdgeUpdate}
      edgeUpdaterRadius={14}
      onEdgesChange={onEdgesChange}
      onNodeClick={(_, node) => {
        if (!isSourceNode(node.id)) onSelectStep(node.id);
      }}
      fitView
      // Refit when the graph is re-parented into the overlay, so opening
      // fullscreen frames the whole workflow instead of keeping the inline
      // viewport's crop.
      key={expanded ? "expanded" : "inline"}
      fitViewOptions={FIT_VIEW_OPTIONS}
      proOptions={{ hideAttribution: true }}
      nodesDraggable
      nodesConnectable
      // Drag anywhere to pan, and reserve the wheel for zoom. Panning by
      // scroll made a two-finger gesture over the canvas fight the studio
      // form scrolling underneath it.
      panOnDrag
      panOnScroll={false}
      zoomOnScroll
      zoomOnDoubleClick={false}
      minZoom={0.25}
      maxZoom={1.75}
      deleteKeyCode={["Backspace", "Delete"]}
    >
      <Background gap={18} size={1} />
      <Controls showInteractive={false} position="bottom-left" />
      {expanded && <MiniMap pannable zoomable
        nodeColor={minimapNodeColor} maskColor="var(--canvas-minimap-mask)" />}
    </ReactFlow>
  );

  const canvas = (
    <div className={`workflow-canvas${expanded ? " is-expanded" : ""}`}>
      <ExecutionMode steps={steps} />
      <div className="workflow-canvas-surface" aria-label="עריכת חיבורי התהליך">
        {graph}
        <button type="button" className="canvas-expand"
          onClick={() => setExpanded((current) => !current)}
          aria-expanded={expanded}
          aria-label={expanded ? "יציאה ממסך מלא" : "עריכה במסך מלא"}
          title={expanded ? "יציאה ממסך מלא (Esc)" : "עריכה במסך מלא"}>
          {expanded
            ? <Minimize2 size={16} aria-hidden="true" />
            : <Maximize2 size={16} aria-hidden="true" />}
        </button>
      </div>
      <p className="canvas-hint">
        גררו משדה פלט אל שלב אחר כדי להזרים אליו את השדה הזה — החיבור קובע
        גם את שדה המזהה. אפשר לגרור קצה של חיבור קיים אל שדה אחר כדי להזיז
        אותו, ומחיקת חיבור מחזירה את השלב למזהה הראשי.
        {expanded && " גרירה על הרקע מזיזה את התצוגה, וגלגלת מקרבת ומרחיקה."}
      </p>
    </div>
  );

  if (!expanded) return canvas;
  // Portalled out of the studio form so the overlay is not clipped by its
  // scroll container. A portal escapes the DOM but not the React tree, so —
  // as with the interview drawer — submit and Enter are stopped here, or
  // deleting a node with the keyboard would submit the draft being edited.
  return createPortal(
    <div className="canvas-overlay" role="dialog" aria-modal="true"
      aria-label="עריכת חיבורי התהליך במסך מלא"
      onSubmit={(event) => event.stopPropagation()}
      onKeyDown={(event) => {
        if (event.key === "Enter") event.stopPropagation();
      }}>
      {canvas}
    </div>,
    document.body);
}

/* ---------- execution mode ---------- */

/**
 * What this graph will actually do when it runs.
 *
 * The engine already supports both modes and needs no flag to pick one: a
 * step with no incoming connection lands in level 0, and the backend runs a
 * whole level concurrently in a thread pool. So a workflow with nothing
 * connected *is* a parallel bundle of tools, and one long chain is a
 * pipeline. What was missing is that the canvas never said so — every
 * unconnected step is drawn as an edge from the main identifier, which
 * reads like a fan-out chain rather than a deliberate choice.
 */
function ExecutionMode({ steps }: { steps: WorkflowStep[] }) {
  const levels = stepLevels(steps);
  if (!levels.length) return null;
  const mode = executionMode(levels);
  return (
    <div className={`canvas-mode is-${mode.kind}`}>
      <span className="canvas-mode-icon">
        {mode.kind === "chain"
          ? <GitCommitHorizontal size={15} aria-hidden="true" />
          : <Rows3 size={15} aria-hidden="true" />}
      </span>
      <p><strong>{mode.title}</strong> <span>{mode.detail}</span></p>
      {/* The shape of the run, as a row per level. A level's width is how
          many packages fire at once, which is the fact an FDE is weighing
          when they decide whether to connect two steps at all. */}
      <ol className="canvas-mode-levels" aria-label="שלבי ריצה">
        {levels.map((level, index) =>
          <li key={index}>
            <b>{index + 1}</b>
            <span>{level.length > 1
              ? `${level.length} טולים במקביל` : level[0].name || level[0].key}
            </span>
          </li>)}
      </ol>
    </div>
  );
}

type ExecutionModeInfo = {
  kind: "bundle" | "chain" | "mixed";
  title: string;
  detail: string;
};

function executionMode(levels: WorkflowStep[][]): ExecutionModeInfo {
  const total = levels.reduce((count, level) => count + level.length, 0);
  const widest = Math.max(...levels.map((level) => level.length));
  if (levels.length === 1) {
    return total === 1
      ? { kind: "bundle", title: "טול יחיד",
          detail: "שלב אחד, ללא תלויות." }
      : { kind: "bundle", title: "חבילת טולים מקבילה",
          detail: `כל ${total} הטולים רצים יחד על המזהה הראשי.` };
  }
  if (widest === 1) {
    return { kind: "chain", title: "שרשרת",
      detail: `${levels.length} שלבים, כל אחד ממתין לקודם.` };
  }
  return { kind: "mixed", title: "משולב",
    detail: `${levels.length} שלבי ריצה; הרחב ביותר מריץ ${widest} טולים במקביל.` };
}

const FIT_VIEW_OPTIONS = { padding: 0.18, maxZoom: 1 };

/** Minimap tint: the step's state, matching the node borders it stands for. */
function minimapNodeColor(node: Node) {
  if (isSourceNode(node.id)) return "var(--border-strong)";
  return (node.data as StepNodeData)?.incomplete
    ? "var(--warning)" : "var(--primary)";
}

/**
 * Hold the page still behind the overlay.
 *
 * The canvas covers the viewport, so a wheel gesture that misses it would
 * otherwise scroll the studio form underneath and leave the FDE somewhere
 * else entirely once they closed fullscreen. The previous inline value is
 * restored rather than assumed to be `""`.
 */
function useLockedBodyScroll(active: boolean) {
  useEffect(() => {
    if (!active) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, [active]);
}

/** Esc leaves fullscreen, the exit every overlay is expected to have. */
function useEscapeToClose(active: boolean, onClose: () => void) {
  useEffect(() => {
    if (!active) return;
    const handle = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, [active, onClose]);
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

/**
 * One step, showing the tool it runs and the output that tool produces.
 *
 * The output list is the point of the node: wiring a step is choosing one
 * field out of another step's output, and until that list was on the canvas
 * an FDE had to open the step form to remember what a tool even emits.
 * Fields consumed downstream are marked, so a glance answers both "what does
 * this produce" and "what is actually being used".
 */
function StepNode({ data }: NodeProps<StepNodeData>) {
  return (
    <div className={`canvas-node canvas-node-step${
      data.selected ? " is-selected" : ""}${data.incomplete ? " is-incomplete" : ""}`}>
      <Handle type="target" position={Position.Right} />
      <header className="canvas-node-head">
        <span className="canvas-node-icon">
          <Package size={15} aria-hidden="true" />
        </span>
        <div>
          <strong>{data.name}</strong>
          <small dir="ltr">{data.packageName}</small>
        </div>
      </header>
      {data.incompleteReason && <p className="canvas-node-warning">
        <AlertTriangle size={12} aria-hidden="true" />
        {data.incompleteReason}
      </p>}
      <OutputFieldList data={data} />
    </div>
  );
}

/**
 * The tool's output contract — and the connection points themselves.
 *
 * Every field carries its own source handle, so dragging from `site_id` to
 * another step sets both `input_source` and `input_field` in one gesture.
 * The field a step reads used to be a separate dropdown, which meant wiring
 * a step was two disconnected acts: draw the edge, then remember which field
 * carried the identifier.
 */
function OutputFieldList({ data }: { data: StepNodeData }) {
  if (!data.outputFields.length) {
    return (
      <p className="canvas-node-empty">
        {data.packageChosen
          ? "לטול אין עדיין חוזה פלט או דוגמאות"
          : "בחרו טול כדי לראות את הפלט"}
        {/* Without a contract there is still something to connect: the whole
            output, with the field named by hand in the step form. */}
        <Handle type="source" position={Position.Left}
          id={ANY_FIELD_HANDLE} />
      </p>
    );
  }
  return (
    <ul className="canvas-node-fields" dir="ltr">
      {data.outputFields.map((field) =>
        <li key={field.name}
          className={field.consumed ? "is-consumed" : undefined}>
          <b>{field.name}</b>
          <span>{field.type}</span>
          <Handle type="source" position={Position.Left} id={field.name}
            title={`חיבור מהשדה ${field.name}`} />
        </li>)}
      {data.hiddenFieldCount > 0 && <li className="canvas-node-more" dir="rtl">
        ועוד {data.hiddenFieldCount} שדות
      </li>}
    </ul>
  );
}

/** Source handle for a package with no declared output contract. */
const ANY_FIELD_HANDLE = "*";

type OutputField = { name: string; type: string; consumed: boolean };

type StepNodeData = {
  name: string;
  packageName: string;
  packageChosen: boolean;
  outputFields: OutputField[];
  hiddenFieldCount: number;
  selected: boolean;
  incomplete: boolean;
  incompleteReason: string;
};

const NODE_TYPES = { sourceNode: SourceNode, stepNode: StepNode };

function canvasNodes(
  steps: WorkflowStep[], packages: PackageVersion[], selectedKey: string,
): Node[] {
  const levels = stepLevels(steps);
  const sources: Node[] = SOURCE_NODES.map((item, index) => ({
    id: item.id,
    type: "sourceNode",
    position: { x: 0, y: index * 96 },
    data: item,
    draggable: true,
  }));
  const stepNodes: Node[] = [];
  levels.forEach((level, column) => {
    // Nodes in a column vary in height with their field list, so rows are
    // stacked by measuring what came before rather than by a fixed pitch —
    // a uniform pitch overlapped tall nodes onto the one below.
    let offset = 0;
    level.forEach((step) => {
      const data = stepNodeData(step, steps, packages, selectedKey);
      stepNodes.push({
        id: step.key,
        type: "stepNode",
        // RTL reads right-to-left, but React Flow's x axis does not flip, so
        // the layout runs left-to-right and the handles are mirrored instead.
        position: { x: 290 * (column + 1), y: offset },
        data,
        draggable: true,
      });
      offset += nodeHeight(data) + 26;
    });
  });
  return [...sources, ...stepNodes];
}

/** Approximate rendered height, used only to space a column's rows. */
function nodeHeight(data: StepNodeData): number {
  const rows = data.outputFields.length + (data.hiddenFieldCount > 0 ? 1 : 0);
  const body = rows ? rows * 19 + 8 : 26;
  return 52 + body + (data.incompleteReason ? 22 : 0);
}

const VISIBLE_FIELD_LIMIT = 6;

function stepNodeData(
  step: WorkflowStep, steps: WorkflowStep[], packages: PackageVersion[],
  selectedKey: string,
): StepNodeData {
  const item = packages.find((candidate) => candidate.id === step.package_version_id);
  const consumed = consumedFields(step.key, steps);
  const fields = outputFields(item).map((field) => ({
    ...field, consumed: consumed.has(field.name),
  }));
  // A consumed field must stay visible even past the cap, or the node hides
  // the one field the FDE most needs to see: the one carrying the next step.
  const shown = prioritized(fields);
  return {
    name: step.name || step.key,
    packageName: item ? `${item.name} · v${item.version}` : "לא נבחר טול",
    packageChosen: Boolean(item),
    outputFields: shown,
    hiddenFieldCount: fields.length - shown.length,
    selected: step.key === selectedKey,
    incomplete: Boolean(incompleteReason(step)),
    incompleteReason: incompleteReason(step),
  };
}

/** Why this step cannot be published yet, or "" when it is complete. */
function incompleteReason(step: WorkflowStep): string {
  if (!step.package_version_id) return "לא נבחר טול";
  if (mappedStep(step) && !step.input_field.trim()) return "לא נבחר שדה מזהה";
  return "";
}

/** Field names of this step's output that a later step reads. */
function consumedFields(key: string, steps: WorkflowStep[]): Set<string> {
  return new Set(steps
    .filter((step) => step.input_source === `steps.${key}`)
    .map((step) => step.input_field.trim())
    .filter(Boolean));
}

function prioritized(fields: OutputField[]): OutputField[] {
  if (fields.length <= VISIBLE_FIELD_LIMIT) return fields;
  const consumed = fields.filter((field) => field.consumed);
  const rest = fields.filter((field) => !field.consumed);
  return [...consumed, ...rest].slice(0, VISIBLE_FIELD_LIMIT);
}

/**
 * A package's output fields with their declared types.
 *
 * Mirrors the backend's `_output_fields`: schema properties unioned with the
 * keys actually seen in the examples, so the canvas, the field picker, and
 * the planning agent all agree on what a tool emits.
 */
function outputFields(item?: PackageVersion): OutputField[] {
  if (!item) return [];
  const schema = item.output_schema as {
    properties?: Record<string, { type?: unknown }>;
  };
  const properties = schema?.properties;
  const types = new Map<string, string>();
  if (properties && typeof properties === "object") {
    Object.entries(properties).forEach(([name, definition]) =>
      types.set(name, fieldType(definition)));
  }
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

/** A schema type, which may be a union the backend emitted as an array. */
function fieldType(definition: { type?: unknown }): string {
  const type = definition && typeof definition === "object"
    ? definition.type : undefined;
  if (Array.isArray(type)) return type.filter(Boolean).join(" | ");
  return typeof type === "string" ? type : "";
}

/* ---------- edges ---------- */

function canvasEdges(
  steps: WorkflowStep[], packages: PackageVersion[],
): Edge[] {
  return steps.map((step) => {
    const source = step.input_source || ROOT_SOURCE;
    const from = source.startsWith("steps.") ? source.split(".")[1] : source;
    return {
      id: edgeId(from, step.key),
      source: from,
      target: step.key,
      // Anchor on the field's own handle so the string visibly leaves the
      // value it carries, not the node as a whole. A mapping naming a field
      // the source no longer emits has no handle to anchor to, and falls
      // back to the node so the edge stays visible instead of vanishing.
      sourceHandle: sourceHandleFor(step, from, steps, packages),
      label: mappedStep(step) && !step.input_field.trim() ? "?" : "",
      markerEnd: { type: MarkerType.ArrowClosed },
      animated: mappedStep(step),
      updatable: true,
      // An edge from a workflow-level input is not a mapping the FDE built;
      // it is every unconnected step's default. Drawn faintly so a bundle of
      // parallel tools does not read as a deliberate fan-out chain, and the
      // real mappings stand out against it.
      className: mappedStep(step) ? undefined : "is-implicit",
    };
  });
}

/** The handle a step's incoming edge should leave from, or null for a node. */
function sourceHandleFor(
  step: WorkflowStep, from: string, steps: WorkflowStep[],
  packages: PackageVersion[],
): string | null {
  if (isSourceNode(from)) return null;
  const field = step.input_field.trim();
  const source = steps.find((candidate) => candidate.key === from);
  const item = packages.find(
    (candidate) => candidate.id === source?.package_version_id);
  const fields = outputFields(item);
  if (!fields.length) return ANY_FIELD_HANDLE;
  return fields.some((candidate) => candidate.name === field) ? field : null;
}

const EDGE_SEPARATOR = "~>";

function edgeId(from: string, to: string) {
  return `${from}${EDGE_SEPARATOR}${to}`;
}

function targetOfEdge(id: string) {
  return id.split(EDGE_SEPARATOR)[1] ?? "";
}

/**
 * The output field a drag started from.
 *
 * The workflow-level sources and a package with no contract carry no field:
 * `workflow.id` and `workflow.boundaries` are complete inputs on their own,
 * and `_validate_source` only demands an `input_field` for a `steps.<key>`
 * source, which the step form is then left to fill in.
 */
function connectedField(handle: string | null | undefined): string {
  if (!handle || handle === ANY_FIELD_HANDLE) return "";
  return handle;
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
