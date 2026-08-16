"use client";

import type { AgentContent, PackageVersion, WorkflowVersion } from "@/types";
import WorkflowForm from "./workflow/WorkflowForm";
import WorkflowLibrary from "./workflow/WorkflowLibrary";
import { useWorkflowEditor } from "./workflow/useWorkflowEditor";

export default function WorkflowEditor({
  packages,
  workflows,
  agents,
  onRefresh,
}: {
  packages: PackageVersion[];
  workflows: WorkflowVersion[];
  agents: AgentContent[];
  onRefresh: () => Promise<void>;
}) {
  const editor = useWorkflowEditor(packages, onRefresh);
  return (
    <div className="workflow-studio">
      <WorkflowLibrary workflows={workflows} editor={editor} />
      <WorkflowForm packages={packages} agents={agents} editor={editor} />
    </div>
  );
}
