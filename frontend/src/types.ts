export type RunStatus = "queued" | "running" | "completed" | "partial" | "failed";

export interface SummarySection {
  workflow_id: string;
  workflow_key: string;
  name: string;
  status: "completed" | "partial" | "failed";
  summary: string;
  /** What this section rests on, stated rather than left to be inferred. */
  coverage?: string;
  facts: string[];
  /** Distributions and ranges, kept apart from individual facts. */
  patterns?: string[];
  outliers?: string[];
  warnings: string[];
  suggested_questions: string[];
  /** Extra fields declared by the workflow's own output_schema. */
  fields?: Record<string, unknown>;
  /** The model did not answer; the text is counts, not a summary. */
  degraded?: boolean;
  evidence_ids: string[];
  agent_key?: string;
}

export type AgentPhase =
  | "delegating"
  | "running_workflows"
  | "questioning"
  | "synthesizing"
  | "completed";

export interface SpecialistAnswer {
  round: number;
  question: string;
  answer: string;
  findings: string[];
  limitations: string[];
  evidence_ids: string[];
  status: "completed" | "failed";
}

export interface SpecialistTrace {
  agent_id: string;
  agent_key: string;
  version: number;
  name: string;
  task: string;
  status: "planned" | "running" | "completed" | "partial" | "failed";
  workflow_ids: string[];
  workflow_keys: string[];
  skill_ids: string[];
  skill_keys: string[];
  answers: SpecialistAnswer[];
  error: string;
}

export interface AgentTrace {
  phase: AgentPhase;
  max_rounds: number;
  rounds_used: number;
  specialists: SpecialistTrace[];
  missing_data?: string[];
}

export interface SummaryResult {
  /** One-line answer, shown before any detail. */
  headline?: string;
  summary: string;
  coverage?: string;
  key_findings: string[];
  risks: string[];
  missing_data: string[];
  suggested_questions: string[];
  skill_results: SkillResult[];
  sections: SummarySection[];
  partial: boolean;
  degraded?: boolean;
  needs_clarification?: boolean;
  /** On a clarification: what the agent would look at first, and why. */
  recommendation?: string;
  /** Clickable answers to the clarifying question. Empty when the honest
      answers were not a short list — free text stays the way out. */
  options?: ClarifyOption[];
  agent_trace?: AgentTrace;
}

export interface ClarifyOption {
  /** Short button caption. */
  label: string;
  /** Sent verbatim as the user's next question. */
  answer: string;
}

export interface SummaryRun {
  id: string;
  conversation_id: string;
  kind: "full" | "follow_up";
  question: string;
  skill_keys: string[];
  status: RunStatus;
  progress: {
    completed: number;
    total: number;
    sections: SummarySection[];
    phase?: AgentPhase;
    agent_trace?: AgentTrace;
  };
  result: SummaryResult | null;
  error: string;
  created_at: string;
}

export interface SummarySkill {
  content_key: string;
  name: string;
  description: string;
}

export interface SkillResult {
  skill_key: string;
  name: string;
  summary: string;
  items: string[];
  sources: string[];
}

/** Result of testing unsaved Skill instructions against sample sections. */
export interface SkillPreviewResult {
  result: SkillResult;
  /** Sections the Skill cited that do not exist — dropped before display. */
  dropped_sources: string[];
}

export interface Conversation {
  id: string;
  root_id: string;
  /** The opening question. Empty on conversations created before titles. */
  title?: string;
  created_at: string;
  updated_at: string;
  last_status?: RunStatus;
  runs?: SummaryRun[];
}

/** One finished turn of a conversation, projected from its run. */
export interface ConversationTurn {
  run_id: string;
  question: string;
  answer: string;
  status: RunStatus;
  created_at: string;
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
  timeout_seconds?: number | null;
  agent_enabled: boolean;
  agent_instructions: string;
  output_schema: Record<string, unknown>;
  example_input: string[];
  example_output: Array<Record<string, unknown>>;
}

export interface PackageInspection {
  row_count: number;
  records: Array<Record<string, unknown>>;
  truncated: boolean;
  output_schema: Record<string, unknown>;
  metadata_suggestions: {
    description: string;
    agent_instructions: string;
  };
}

export interface WorkflowStep {
  key: string;
  name: string;
  package_version_id: string;
  depends_on: string[];
  input_source: string;
  input_field: string;
  input_value: string;
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

export interface MissingTool {
  name: string;
  reason: string;
  input_description: string;
  output_description: string;
}

export interface WorkflowPlan {
  can_build: boolean;
  name: string;
  description: string;
  role: "baseline" | "detail" | "both";
  rationale: string;
  system_prompt: string;
  steps: WorkflowStep[];
  missing_tools: MissingTool[];
}

export interface PlanChatMessage {
  role: "fde" | "agent";
  text: string;
}

/** Fields the tool planner fills while discussing the data with the FDE. */
export interface ToolPlanDraft {
  name: string;
  package_id: string;
  input_cube_name: string;
  input_cube_parameter: string;
  output_cube_name: string;
  input_mode: "single" | "many" | "";
  description: string;
  agent_instructions: string;
  package_key: string;
  query_name: string;
  agent_enabled: boolean;
  /** JSON text, so the FDE edits it in the same textarea as always. */
  output_schema: string;
  example_input: string;
  example_output: string;
}

/** One answer offered for clicking, instead of typing it. */
export interface PlanOption {
  /** The button caption. */
  label: string;
  /** Sent verbatim as the FDE's message when the option is clicked. */
  answer: string;
}

/** The single question a turn may ask, always with a recommended answer. */
export interface PlanQuestion {
  question: string;
  recommendation: string;
  why: string;
  /**
   * Concrete answers to click, the first being `recommendation`. Empty
   * whenever the honest answer is open-ended, so the composer is the only
   * way to reply — never assume there is something to click.
   */
  options: PlanOption[];
}

interface PlanChatTurn {
  reply: string;
  /** Null once the interview has nothing left to ask. */
  question: PlanQuestion | null;
  resolved: string[];
  open_points: string[];
  /** The agent is presenting its summary and waiting for the FDE to confirm. */
  awaiting_confirmation: boolean;
  /** Confirmed and safe to load into the form; never true while asking. */
  ready: boolean;
}

export interface ToolPlanChatTurn extends PlanChatTurn {
  /**
   * Retained for the wire contract only. The interview now opens on a sample
   * the FDE already ran, so there is nothing left for it to request.
   */
  needs_inspection: boolean;
  draft: ToolPlanDraft;
}

export interface WorkflowPlanChatTurn extends PlanChatTurn {
  draft: WorkflowPlan;
}

export interface AgentContent {
  id: string;
  content_key: string;
  version: number;
  kind: "skill" | "prompt" | "agent";
  name: string;
  description: string;
  content: string;
  config?: {
    workflow_keys: string[];
    skill_keys: string[];
  };
  user_selectable: boolean;
  status: "draft" | "published" | "archived";
}

export interface Evidence {
  id: string;
  workflow_id: string;
  step_key: string;
  row_count: number;
  created_at: string;
}

export interface EvidencePage extends Evidence {
  records: Array<Record<string, unknown>>;
  offset: number;
  limit: number;
  has_more: boolean;
}
