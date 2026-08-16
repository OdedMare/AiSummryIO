import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  Connection,
  Edge,
  EdgeChange,
  NodeChange,
  XYPosition,
} from "reactflow";
import type { PackageVersion, WorkflowStep } from "@/types";
import {
  canvasEdges,
  canvasNodes,
  mergeMeasurements,
  type NodeSize,
} from "./canvasGraph";
import {
  AREA_SOURCE,
  connectedField,
  createsCycle,
  isSourceNode,
  ROOT_SOURCE,
  sourceExpression,
  targetOfEdge,
  VALUE_SOURCE,
} from "./workflowGraph";

export function useWorkflowCanvas({
  steps,
  packages,
  selectedKey,
  onConnectStep,
  onDisconnectStep,
  onRemoveStep,
}: {
  steps: WorkflowStep[];
  packages: PackageVersion[];
  selectedKey: string;
  onConnectStep: (
    targetKey: string,
    source: string,
    inputField: string,
  ) => void;
  onDisconnectStep: (targetKey: string) => void;
  onRemoveStep: (key: string) => void;
}) {
  const [moved, setMoved] = useState<Record<string, XYPosition>>({});
  const [sizes, setSizes] = useState<Record<string, NodeSize>>({});
  const [expanded, setExpanded] = useState(false);
  useEscapeToClose(expanded, () => setExpanded(false));
  useLockedBodyScroll(expanded);

  const live = useMemo(() => {
    const keys = new Set<string>([
      ...steps.map((step) => step.key),
      ROOT_SOURCE,
      AREA_SOURCE,
      VALUE_SOURCE,
    ]);
    return Object.fromEntries(Object.entries(moved)
      .filter(([key]) => keys.has(key)));
  }, [moved, steps]);

  const derived = useMemo(
    () => canvasNodes(steps, packages, selectedKey, live),
    [steps, packages, selectedKey, live],
  );
  const nodes = useMemo(
    () => mergeMeasurements(derived, sizes),
    [derived, sizes],
  );
  const edges = useMemo(
    () => canvasEdges(steps, packages),
    [steps, packages],
  );

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    const positions: Record<string, XYPosition> = {};
    const measured: Record<string, NodeSize> = {};
    changes.forEach((change) => {
      if (change.type === "position" && change.position) {
        positions[change.id] = change.position;
      }
      if (change.type === "dimensions" && change.dimensions) {
        measured[change.id] = change.dimensions;
      }
      if (change.type === "remove" && !isSourceNode(change.id)) {
        onRemoveStep(change.id);
      }
    });
    if (Object.keys(positions).length) {
      setMoved((current) => ({ ...current, ...positions }));
    }
    if (Object.keys(measured).length) {
      setSizes((current) => ({ ...current, ...measured }));
    }
  }, [onRemoveStep]);

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

  const onEdgeUpdate = useCallback((
    previous: Edge,
    connection: Connection,
  ) => {
    if (!connection.source || !connection.target) return;
    if (connection.source === connection.target) return;
    if (createsCycle(steps, connection.source, connection.target)) return;
    if (previous.target !== connection.target) {
      onDisconnectStep(previous.target);
    }
    onConnectStep(
      connection.target,
      sourceExpression(connection.source),
      connectedField(connection.sourceHandle),
    );
  }, [steps, onConnectStep, onDisconnectStep]);

  return {
    nodes,
    edges,
    onNodesChange,
    onConnect,
    onEdgesChange,
    onEdgeUpdate,
    expanded,
    setExpanded,
    hasMoved: Object.keys(live).length > 0,
    resetLayout: () => setMoved({}),
  };
}

function useLockedBodyScroll(active: boolean) {
  useEffect(() => {
    if (!active) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, [active]);
}

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
