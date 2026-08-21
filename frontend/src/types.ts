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

export interface RunQuality {
  score: number;
  level: "high" | "medium" | "low";
  section_coverage: number;
  citation_coverage: number;
  passed: boolean;
  reasons: string[];
}

export interface RunTelemetry {
  model: string;
  prompt_revision: string;
  duration_ms: number;
  tool_calls: number;
  evidence_rows: number;
  workflow_count: number;
  specialist_count: number;
  rounds_used: number;
  degraded: boolean;
  token_usage_available: boolean;
}

export interface RouteDecision {
  action: "use_cached" | "workflow" | "tool" | "clarify";
  workflow_key?: string | null;
  tool_version_id?: string | null;
  confidence: number;
  source: string;
}

/**
 * One source a claim rests on — the public citation, never the internal
 * record. It carries enough to render a marker and to open the exact evidence
 * behind it; the rows themselves come from the evidence endpoints.
 */
export interface Citation {
  citation_id: string;
  evidence_id: string;
  /** The source record this resolves to. */
  source_id: string;
  workflow_id: string;
  workflow_key: string;
  step_key: string;
  /** Human label for the source: the workflow's name, or its step. */
  label: string;
  /** Field names the source supports, not their values. */
  fields: string[];
  /** A short rendering of the first record, for recognizing it inline. */
  excerpt: string;
  row_count: number;
}

/** One factual statement from the answer and the citations supporting it. */
export interface SummaryClaim {
  text: string;
  citation_ids: string[];
}

/** A citation resolved to its bounded source rows. */
export interface CitationRecord extends Citation {
  run_id: string;
  records: Array<Record<string, unknown>>;
}

/** What `GET /conversations/{id}/citations/{citation_id}` returns. */
export interface CitationResolution {
  citation: Citation;
  record: EvidencePage;
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
  /** Claims traced to sources. Absent on summaries produced before
      citations existed, which render as plain text. */
  claims?: SummaryClaim[];
  /** Every source this answer can cite. Empty when nothing was traced. */
  citations?: Citation[];
  /** Records returned directly by a "show me that record" follow-up. */
  cited_records?: CitationRecord[];
  partial: boolean;
  degraded?: boolean;
  needs_clarification?: boolean;
  /** On a clarification: what the agent would look at first, and why. */
  recommendation?: string;
  /** Clickable answers to the clarifying question. Empty when the honest
      answers were not a short list — free text stays the way out. */
  options?: ClarifyOption[];
  agent_trace?: AgentTrace;
  quality?: RunQuality;
  telemetry?: RunTelemetry;
  route_decision?: RouteDecision;
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
  agent_keys: string[];
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

export interface SummaryAgent {
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
  project_id?: string | null;
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
  name: string;
  description: string;
  role: "baseline" | "detail" | "both";
  /** Whether the agent may select this route. There is no publishing step. */
  agent_enabled: boolean;
  /** Specialist owner; null keeps the workflow in direct/non-agent mode. */
  agent_id: string | null;
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

export interface SkillPlanDraft {
  name: string;
  description: string;
  content: string;
  user_selectable: boolean;
  agent_enabled: boolean;
}

export interface SpecialistPlanDraft {
  name: string;
  description: string;
  content: string;
  agent_enabled: boolean;
  workflow_keys: string[];
  skill_keys: string[];
}

export interface SkillPlanChatTurn extends PlanChatTurn {
  draft: SkillPlanDraft;
}

export interface SpecialistPlanChatTurn extends PlanChatTurn {
  draft: SpecialistPlanDraft;
}

export interface AgentContent {
  id: string;
  content_key: string;
  kind: "skill" | "prompt" | "agent";
  name: string;
  description: string;
  content: string;
  config?: {
    workflow_keys: string[];
    skill_keys: string[];
  };
  user_selectable: boolean;
  agent_enabled: boolean;
}

export interface ProjectWorkspace {
  id: string;
  name: string;
  mission: string;
  tool_keys: string[];
  workflow_keys: string[];
  skill_keys: string[];
  agent_keys: string[];
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

export type ProjectDraft = Pick<
  ProjectWorkspace,
  | "name"
  | "mission"
  | "tool_keys"
  | "workflow_keys"
  | "skill_keys"
  | "agent_keys"
>;

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

export type EvaluationStatus =
  | "running"
  | "pausing"
  | "paused"
  | "stopping"
  | "stopped"
  | "completed";

export type EvaluationCaseStatus =
  | "pending"
  | RunStatus
  | "stopped";

export interface EvaluationBatch {
  id: string;
  project_id?: string | null;
  label: string;
  question: string;
  skill_keys: string[];
  agent_keys: string[];
  cooldown_seconds: number;
  status: EvaluationStatus;
  total: number;
  pending: number;
  queued: number;
  running: number;
  completed: number;
  partial: number;
  failed: number;
  stopped: number;
  reviewed: number;
  average_rating: number | null;
  automatic_quality: number | null;
  created_at: string;
  updated_at: string;
  finished_at: string | null;
}

export interface EvaluationCase {
  id: string;
  batch_id: string;
  position: number;
  root_id: string;
  status: EvaluationCaseStatus;
  rating: 1 | 2 | 3 | 4 | 5 | null;
  comment: string;
  error: string;
  headline: string | null;
  summary: string | null;
  duration_seconds: number | null;
  run_id: string | null;
}

export interface EvaluationCaseDetail extends EvaluationCase {
  conversation_id: string | null;
  kind: "full" | null;
  question: string | null;
  skill_keys: string[] | null;
  agent_keys: string[] | null;
  run_status: RunStatus | null;
  progress: SummaryRun["progress"] | null;
  result: SummaryResult | null;
  run_created_at: string | null;
  finished_at: string | null;
}

export interface EvaluationCasePage {
  items: EvaluationCase[];
  total: number;
  offset: number;
  limit: number;
}

export interface EvaluationImport {
  root_ids: string[];
  sheet: string;
  column: string;
  warnings: string[];
}
