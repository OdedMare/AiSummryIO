"use client";

import type { PackageVersion, WorkflowVersion } from "@/types";
import WorkflowForm from "./workflow/WorkflowForm";
import WorkflowLibrary from "./workflow/WorkflowLibrary";
import { useWorkflowEditor } from "./workflow/useWorkflowEditor";

export default function WorkflowEditor({
  packages,
  workflows,
  onRefresh,
}: {
  packages: PackageVersion[];
  workflows: WorkflowVersion[];
  onRefresh: () => Promise<void>;
}) {
  const editor = useWorkflowEditor(packages, onRefresh);
  return (
    <div className="workflow-studio">
      <WorkflowLibrary workflows={workflows} editor={editor} />
      <WorkflowForm packages={packages} editor={editor} />
    </div>
  );
}
