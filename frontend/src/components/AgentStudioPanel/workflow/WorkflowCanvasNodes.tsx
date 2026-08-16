import { AlertTriangle, Map as MapIcon, Package, Tag } from "lucide-react";
import {
  Handle,
  Position,
  type NodeProps,
} from "reactflow";
import type { StepNodeData } from "./canvasGraph";
import { ANY_FIELD_HANDLE } from "./workflowGraph";

function SourceNode({
  data,
}: NodeProps<{ label: string; hint: string }>) {
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
      data.selected ? " is-selected" : ""}${
      data.incomplete ? " is-incomplete" : ""}`}>
      <header className="canvas-node-head">
        <span className="canvas-node-icon">
          <Package size={15} aria-hidden="true" />
        </span>
        <div>
          <strong>{data.name}</strong>
          <small dir="ltr">{data.packageName}</small>
        </div>
      </header>
      <div className="canvas-node-input">
        <span>קלט</span>
        <b dir="ltr">{data.inputName}</b>
        <Handle type="target" position={Position.Right}
          title={`חיבור לקלט ${data.inputName}`} />
      </div>
      {data.incompleteReason && <p className="canvas-node-warning">
        <AlertTriangle size={12} aria-hidden="true" />
        {data.incompleteReason}
      </p>}
      <OutputFieldList data={data} />
    </div>
  );
}

function OutputFieldList({ data }: { data: StepNodeData }) {
  if (!data.outputFields.length) {
    return (
      <p className="canvas-node-empty">
        {data.packageChosen
          ? "לטול אין עדיין חוזה פלט או דוגמאות"
          : "בחרו טול כדי לראות את הפלט"}
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
    </ul>
  );
}

export const WORKFLOW_NODE_TYPES = {
  sourceNode: SourceNode,
  stepNode: StepNode,
};
