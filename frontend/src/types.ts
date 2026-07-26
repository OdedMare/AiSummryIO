export type RunStatus = "queued" | "running" | "completed" | "partial" | "failed";

export interface SummarySection {
  workflow_id: string;
  workflow_key: string;
  name: string;
  status: "completed" | "partial" | "failed";
  summary: string;
  facts: string[];
  warnings: string[];
  suggested_questions: string[];
  /** Extra fields declared by the workflow's own output_schema. */
  fields?: Record<string, unknown>;
  evidence_ids: string[];
}

export interface SummaryResult {
  summary: string;
  key_findings: string[];
  risks: string[];
  missing_data: string[];
  suggested_questions: string[];
  sections: SummarySection[];
  partial: boolean;
  needs_clarification?: boolean;
}

export interface SummaryRun {
  id: string;
  conversation_id: string;
  kind: "full" | "follow_up";
  question: string;
  status: RunStatus;
  progress: {
    completed: number;
    total: number;
    sections: SummarySection[];
  };
  result: SummaryResult | null;
  error: string;
  created_at: string;
}

export interface Conversation {
  id: string;
  root_id: string;
  created_at: string;
  updated_at: string;
  last_status?: RunStatus;
  runs?: SummaryRun[];
}

export interface PackageVersion {
  id: string;
  package_key: string;
  version: number;
  name: string;
  description: string;
  package_id: string;
  input_cube_name: string;
  input_cube_parameter: string;
  input_mode: "single" | "many";
  output_cube_name: string;
  query_name: string;
  example_input: string[];
  example_output: Array<Record<string, unknown>>;
}

export interface WorkflowStep {
  key: string;
  name: string;
  package_version_id: string;
  depends_on: string[];
  input_source: string;
  input_field: string;
  summary_prompt: string;
}

export interface WorkflowVersion {
  id: string;
  workflow_key: string;
  version: number;
  name: string;
  description: string;
  role: "baseline" | "detail" | "both";
  status: "draft" | "published" | "archived";
  system_prompt: string;
  output_schema: Record<string, unknown>;
  examples: Array<Record<string, unknown>>;
  steps: WorkflowStep[];
}

export interface AgentContent {
  id: string;
  content_key: string;
  version: number;
  kind: "skill" | "prompt";
  name: string;
  description: string;
  content: string;
  status: "draft" | "published" | "archived";
}

export interface Evidence {
  id: string;
  workflow_id: string;
  step_key: string;
  records: Array<Record<string, unknown>>;
  created_at: string;
}

