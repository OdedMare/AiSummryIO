"use client";

import { createPortal } from "react-dom";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
} from "reactflow";
import "reactflow/dist/style.css";
import { LayoutGrid, Maximize2, Minimize2 } from "lucide-react";
import type { PackageVersion, WorkflowStep } from "@/types";
import {
  FIT_VIEW_OPTIONS,
  minimapNodeColor,
} from "./workflow/canvasGraph";
import { WORKFLOW_NODE_TYPES } from "./workflow/WorkflowCanvasNodes";
import WorkflowExecutionMode from "./workflow/WorkflowExecutionMode";
import { useWorkflowCanvas } from "./workflow/useWorkflowCanvas";
import { isSourceNode } from "./workflow/workflowGraph";

export { mappedStep, orderedSteps } from "./workflow/workflowGraph";

export default function WorkflowCanvas({
  steps,
  packages,
  onConnectStep,
  onDisconnectStep,
  onSelectStep,
  selectedKey,
  onRemoveStep,
}: {
  steps: WorkflowStep[];
  packages: PackageVersion[];
  onConnectStep: (
    targetKey: string,
    source: string,
    inputField: string,
  ) => void;
  onDisconnectStep: (targetKey: string) => void;
  onSelectStep: (key: string) => void;
  selectedKey: string;
  onRemoveStep: (key: string) => void;
}) {
  const graphState = useWorkflowCanvas({
    steps,
    packages,
    selectedKey,
    onConnectStep,
    onDisconnectStep,
    onRemoveStep,
  });
  const {
    nodes,
    edges,
    onConnect,
    onEdgeUpdate,
    onEdgesChange,
    onNodesChange,
    expanded,
    setExpanded,
    hasMoved,
    resetLayout,
  } = graphState;

  const graph = (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={WORKFLOW_NODE_TYPES}
      onConnect={onConnect}
      onEdgeUpdate={onEdgeUpdate}
      edgeUpdaterRadius={14}
      onEdgesChange={onEdgesChange}
      onNodesChange={onNodesChange}
      onNodeClick={(_, node) => {
        if (!isSourceNode(node.id)) onSelectStep(node.id);
      }}
      fitView
      key={expanded ? "expanded" : "inline"}
      fitViewOptions={FIT_VIEW_OPTIONS}
      proOptions={{ hideAttribution: true }}
      nodesDraggable
      nodesConnectable
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
        nodeColor={minimapNodeColor}
        maskColor="var(--canvas-minimap-mask)" />}
    </ReactFlow>
  );

  const canvas = (
    <div className={`workflow-canvas${expanded ? " is-expanded" : ""}`}>
      <WorkflowExecutionMode steps={steps} />
      <div className="workflow-canvas-surface" aria-label="עריכת חיבורי התהליך">
        {graph}
        <div className="canvas-tools">
          {hasMoved && <button type="button" className="canvas-expand"
            onClick={resetLayout} title="סידור אוטומטי מחדש"
            aria-label="סידור אוטומטי מחדש">
            <LayoutGrid size={16} aria-hidden="true" />
          </button>}
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
      </div>
      <p className="canvas-hint">
        גררו משדה פלט אל שלב אחר כדי להזרים אליו את השדה הזה — החיבור קובע
        גם את שדה המזהה. אפשר לגרור קצה של חיבור קיים אל שדה אחר כדי להזיז
        אותו, ומחיקת חיבור מחזירה את השלב למזהה הראשי. גררו שלב כדי למקם
        אותו בחופשיות, ומקש Delete מוחק את השלב שנבחר.
        {expanded && " גרירה על הרקע מזיזה את התצוגה, וגלגלת מקרבת ומרחיקה."}
      </p>
    </div>
  );

  if (!expanded) return canvas;
  return createPortal(
    <div className="canvas-overlay" role="dialog" aria-modal="true"
      aria-label="עריכת חיבורי התהליך במסך מלא"
      onSubmit={(event) => event.stopPropagation()}
      onKeyDown={(event) => {
        if (event.key === "Enter") event.stopPropagation();
      }}>
      {canvas}
    </div>,
    document.body,
  );
}
