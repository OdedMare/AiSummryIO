import { GitCommitHorizontal, Rows3 } from "lucide-react";
import type { WorkflowStep } from "@/types";
import { stepLevels } from "./workflowGraph";

export default function WorkflowExecutionMode({
  steps,
}: {
  steps: WorkflowStep[];
}) {
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
      <ol className="canvas-mode-levels" aria-label="שלבי ריצה">
        {levels.map((level, index) =>
          <li key={index}>
            <b>{index + 1}</b>
            <span>{level.length > 1
              ? `${level.length} טולים במקביל`
              : level[0].name || level[0].key}
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
      ? {
        kind: "bundle",
        title: "טול יחיד",
        detail: "שלב אחד, ללא תלויות.",
      }
      : {
        kind: "bundle",
        title: "חבילת טולים מקבילה",
        detail: `כל ${total} הטולים רצים יחד על המזהה הראשי.`,
      };
  }
  if (widest === 1) {
    return {
      kind: "chain",
      title: "שרשרת",
      detail: `${levels.length} שלבים, כל אחד ממתין לקודם.`,
    };
  }
  return {
    kind: "mixed",
    title: "משולב",
    detail: `${levels.length} שלבי ריצה; הרחב ביותר מריץ ${widest} טולים במקביל.`,
  };
}
