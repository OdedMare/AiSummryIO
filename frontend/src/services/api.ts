import type {
  AgentContent, CitationResolution, Conversation, ConversationTurn,
  Evidence, EvidencePage,
  EvaluationBatch, EvaluationCaseDetail, EvaluationCasePage, EvaluationImport,
  PackageInspection,
  PackageVersion, PlanChatMessage, ProjectDraft, ProjectWorkspace,
  SkillPreviewResult, SummaryRun,
  SkillPlanChatTurn, SkillPlanDraft, SpecialistPlanChatTurn, SummaryAgent,
  SpecialistPlanDraft, SummarySkill, ToolPlanChatTurn, ToolPlanDraft,
  WorkflowPlan, WorkflowPlanChatTurn, WorkflowVersion,
} from "@/types";
import type { GeoJSONMultiPolygon } from "@/types/geo";

/**
 * Every backend call is traced to the browser console.
 *
 * Failures are logged with the request body that caused them, because the
 * Hebrew message the UI shows is deliberately short and a 4xx/5xx is only
 * diagnosable next to what was actually sent.
 */
export async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const method = options?.method ?? "GET";
  const started = performance.now();
  const label = `${method} ${path}`;
  // The 1.5s run/evaluation polls would drown the console, so they are logged
  // only when they fail or turn slow.
  const quiet = method === "GET" && /^\/api\/(?:runs|evaluations)(?:\/|\?|$)/.test(path);
  if (!quiet) console.debug(`[api] → ${label}`, requestBody(options));

  let response: Response;
  try {
    response = await fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", ...options?.headers },
      credentials: "same-origin",
    });
  } catch (reason) {
    // A network-level failure never reaches the code below, so it would
    // otherwise surface as a bare "Failed to fetch" with no route attached.
    console.error(`[api] ✗ ${label} network error`, reason);
    throw reason;
  }

  const elapsed = performance.now() - started;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    console.error(
      `[api] ✗ ${label} → ${response.status} (${elapsed.toFixed(0)}ms)`,
      { status: response.status, body: data, sent: requestBody(options) },
    );
    throw new Error(errorDetail(data, response.status));
  }
  if (!quiet || elapsed > 3000) {
    console.debug(
      `[api] ✓ ${label} → ${response.status} (${elapsed.toFixed(0)}ms)`, data,
    );
  }
  return data as T;
}

/** The parsed request body, for logging only; never throws on bad JSON. */
function requestBody(options?: RequestInit): unknown {
  if (typeof options?.body !== "string") return undefined;
  try {
    return JSON.parse(options.body);
  } catch {
    return options.body;
  }
}

// A rejected body can still arrive as FastAPI's list of error objects, which
// would render as "[object Object]" if passed to Error directly.
function errorDetail(data: unknown, status: number): string {
  const fallback = `הבקשה נכשלה (${status})`;
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail.trim() || fallback;
  if (Array.isArray(detail)) {
    const parts = detail.map(detailEntry).filter(Boolean);
    return parts.length ? parts.join("; ") : fallback;
  }
  if (detail && typeof detail === "object") return detailEntry(detail) || fallback;
  return fallback;
}

function detailEntry(entry: unknown): string {
  if (typeof entry === "string") return entry.trim();
  if (!entry || typeof entry !== "object") return "";
  const { loc, msg } = entry as { loc?: unknown; msg?: unknown };
  if (typeof msg !== "string") return "";
  const field = Array.isArray(loc)
    ? loc.filter((part) => part !== "body").join(" → ")
    : "";
  return field ? `${field}: ${msg}` : msg;
}

function scoped(path: string, projectId: string): string {
  return `${path}?project_id=${encodeURIComponent(projectId)}`;
}

export const api = {
  projects: () => request<ProjectWorkspace[]>("/api/projects"),
  createProject: (data: ProjectDraft) =>
    request<ProjectWorkspace>("/api/projects", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateProject: (id: string, data: ProjectDraft) =>
    request<ProjectWorkspace>(`/api/projects/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  deleteProject: (id: string) =>
    request<{ deleted: string; name: string }>(`/api/projects/${id}`, {
      method: "DELETE",
    }),
  conversations: (projectId?: string) => request<Conversation[]>(
    `/api/conversations${projectId
      ? `?project_id=${encodeURIComponent(projectId)}` : ""}`,
  ),
  skills: (projectId: string) =>
    request<SummarySkill[]>(scoped("/api/skills", projectId)),
  conversation: (id: string) =>
    request<Conversation>(`/api/conversations/${id}`),
  deleteConversation: (id: string) =>
    request<{ deleted: string; title: string }>(`/api/conversations/${id}`, {
      method: "DELETE",
    }),
  // The thread as question/answer turns, without the runs' evidence and
  // sections. `conversation` already carries the full runs the transcript
  // renders, so this is for a caller that wants the text alone.
  messages: (id: string) =>
    request<ConversationTurn[]>(`/api/conversations/${id}/messages`),
  specialists: (projectId: string) =>
    request<SummaryAgent[]>(scoped("/api/specialists", projectId)),
  // Either rootId or boundaries must be present; the backend rejects a
  // request carrying neither. A request sent from the map with no identifier
  // typed comes back with `conversation.root_id` set to the drawn area's WKT
  // MULTIPOLYGON — the backend derives it, so the polygon has one serializer
  // rather than one per side of the wire.
  start: (
    rootId: string,
    question: string,
    skillKeys: string[],
    boundaries: GeoJSONMultiPolygon | null = null,
    agentKeys: string[] = [],
    projectId?: string,
  ) =>
    request<{ conversation: Conversation; run: SummaryRun }>("/api/summaries", {
      method: "POST",
      body: JSON.stringify({
        root_id: rootId || null,
        project_id: projectId || null,
        question,
        skill_keys: skillKeys,
        agent_keys: agentKeys,
        boundaries,
      }),
    }),
  // `citationId` is sent when the user asks while a citation or an evidence
  // record is selected, which is what lets "הצג לי את הרשומה הזו" resolve to
  // that exact source instead of being routed as a fresh search. Both
  // citation fields are optional and default to the body this always sent.
  followUp: (
    conversationId: string,
    question: string,
    skillKeys: string[],
    agentKeys: string[] = [],
    citationId: string | null = null,
    referencedCitationIds: string[] = [],
  ) =>
    request<SummaryRun>(`/api/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({
        question, skill_keys: skillKeys, agent_keys: agentKeys,
        citation_id: citationId,
        referenced_citation_ids: referencedCitationIds,
      }),
    }),
  // Resolves one citation inside a conversation the caller owns. Scoped by
  // conversation rather than by citation alone, so the same ownership check
  // the evidence routes apply also guards this one.
  resolveCitation: (conversationId: string, citationId: string, limit = 20) =>
    request<CitationResolution>(
      `/api/conversations/${conversationId}/citations/` +
      `${encodeURIComponent(citationId)}?limit=${limit}`,
    ),
  run: (id: string) => request<SummaryRun>(`/api/runs/${id}`),
  evidence: (id: string) => request<Evidence[]>(`/api/runs/${id}/evidence`),
  evidencePage: (runId: string, evidenceId: string, offset = 0, limit = 100) =>
    request<EvidencePage>(
      `/api/runs/${runId}/evidence/${evidenceId}` +
      `?offset=${offset}&limit=${limit}`,
    ),
  feedback: (runId: string, rating: 1 | 2 | 3 | 4 | 5, comment = "") =>
    request<{ id: string }>("/api/feedback", {
      method: "POST",
      body: JSON.stringify({ run_id: runId, rating, comment }),
    }),
  adminSession: () => request<{ authenticated: boolean }>("/api/admin/session"),
  settings: () => request<Record<string, unknown>>("/api/settings"),
  // Send the CURRENT form values so the check tests what the user typed,
  // before saving. Empty/masked = fall back to the saved value.
  models: (overrides?: { llm_base_url?: string; openai_api_key?: string }) =>
    request<{ models: string[] }>("/api/models", {
      method: "POST",
      body: JSON.stringify(overrides ?? {}),
    }),
  updateSettings: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  packages: (projectId: string) =>
    request<PackageVersion[]>(scoped("/api/packages", projectId)),
  createPackage: (projectId: string, data: Record<string, unknown>) =>
    request<PackageVersion>(scoped("/api/packages", projectId), {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updatePackage: (projectId: string, id: string, data: Record<string, unknown>) =>
    request<PackageVersion>(scoped(`/api/packages/${id}`, projectId), {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  inspectPackage: (projectId: string, data: Record<string, unknown>) =>
    request<PackageInspection>(scoped("/api/packages/inspect", projectId), {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deletePackage: (projectId: string, id: string) =>
    request<{ deleted: string; name: string }>(
      scoped(`/api/packages/${id}`, projectId), {
      method: "DELETE",
    }),
  planToolChat: (
    messages: PlanChatMessage[], draft: Partial<ToolPlanDraft>,
    inspection: PackageInspection | null, projectId: string, focusField = "",
  ) =>
    request<ToolPlanChatTurn>(scoped("/api/packages/plan-chat", projectId), {
      method: "POST",
      body: JSON.stringify({
        messages, draft, inspection: inspection ?? {},
        focus_field: focusField,
      }),
    }),
  workflows: (projectId: string) =>
    request<WorkflowVersion[]>(scoped("/api/workflows", projectId)),
  createWorkflow: (projectId: string, data: Record<string, unknown>) =>
    request<WorkflowVersion>(scoped("/api/workflows", projectId), {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateWorkflow: (projectId: string, id: string, data: Record<string, unknown>) =>
    request<WorkflowVersion>(scoped(`/api/workflows/${id}`, projectId), {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  planWorkflowChat: (
    messages: PlanChatMessage[], draft: WorkflowPlan | null, projectId: string,
    focusField = "",
  ) =>
    request<WorkflowPlanChatTurn>(scoped("/api/workflows/plan-chat", projectId), {
      method: "POST",
      body: JSON.stringify({
        messages, draft: draft ?? {}, focus_field: focusField,
      }),
    }),
  // Evidence from past runs is kept so an existing summary stays traceable.
  deleteWorkflow: (projectId: string, id: string) =>
    request<{ deleted: string; name: string }>(
      scoped(`/api/workflows/${id}`, projectId), {
      method: "DELETE",
    }),
  dryRun: (projectId: string, id: string, rootId: string) =>
    request<Record<string, unknown>>(
      scoped(`/api/workflows/${id}/dry-run`, projectId), {
      method: "POST",
      body: JSON.stringify({ root_id: rootId, question: "בדיקת FDE" }),
    }),
  content: (projectId: string) =>
    request<AgentContent[]>(scoped("/api/agent-content", projectId)),
  createContent: (projectId: string, data: Record<string, unknown>) =>
    request<AgentContent>(scoped("/api/agent-content", projectId), {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateContent: (projectId: string, id: string, data: Record<string, unknown>) =>
    request<AgentContent>(scoped(`/api/agent-content/${id}`, projectId), {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  // A built-in Skill or prompt returns at the next startup; deleting one
  // resets it rather than removing it for good.
  deleteContent: (projectId: string, id: string) =>
    request<{ deleted: string; name: string }>(
      scoped(`/api/agent-content/${id}`, projectId), {
      method: "DELETE",
    }),
  previewSkill: (projectId: string, data: Record<string, unknown>) =>
    request<SkillPreviewResult>(
      scoped("/api/agent-content/preview-skill", projectId), {
      method: "POST",
      body: JSON.stringify(data),
    }),
  planSkillChat: (
    messages: PlanChatMessage[], draft: Partial<SkillPlanDraft>,
    projectId: string, focusField = "",
  ) => request<SkillPlanChatTurn>(
    scoped("/api/agent-content/plan-skill-chat", projectId), {
    method: "POST",
    body: JSON.stringify({ messages, draft, focus_field: focusField }),
  }),
  planSpecialistChat: (
    messages: PlanChatMessage[],
    draft: Partial<SpecialistPlanDraft> & { content_key?: string },
    projectId: string, focusField = "",
  ) => request<SpecialistPlanChatTurn>(
    scoped("/api/agent-content/plan-specialist-chat", projectId),
    {
      method: "POST",
      body: JSON.stringify({ messages, draft, focus_field: focusField }),
    },
  ),
  reviewQueue: () => request<Array<Record<string, unknown>>>("/api/review-queue"),
  evaluations: () => request<EvaluationBatch[]>("/api/evaluations"),
  evaluation: (id: string) =>
    request<EvaluationBatch>(`/api/evaluations/${id}`),
  evaluationCases: (
    id: string, offset = 0, limit = 50, status = "", search = "",
  ) => {
    const query = new URLSearchParams({
      offset: String(offset), limit: String(limit), status, search,
    });
    return request<EvaluationCasePage>(
      `/api/evaluations/${id}/cases?${query.toString()}`,
    );
  },
  evaluationCase: (batchId: string, caseId: string) =>
    request<EvaluationCaseDetail>(
      `/api/evaluations/${batchId}/cases/${caseId}`,
    ),
  createEvaluation: (data: {
    project_id: string;
    label: string;
    root_ids: string[];
    question: string;
    skill_keys: string[];
    agent_keys: string[];
    cooldown_seconds: number;
  }) => request<EvaluationBatch>("/api/evaluations", {
    method: "POST", body: JSON.stringify(data),
  }),
  importEvaluation: (file: File) =>
    request<EvaluationImport>("/api/evaluations/import", {
      method: "POST",
      headers: { "Content-Type": file.type ||
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
      body: file,
    }),
  pauseEvaluation: (id: string) =>
    request<EvaluationBatch>(`/api/evaluations/${id}/pause`, { method: "POST" }),
  resumeEvaluation: (id: string) =>
    request<EvaluationBatch>(`/api/evaluations/${id}/resume`, { method: "POST" }),
  stopEvaluation: (id: string) =>
    request<EvaluationBatch>(`/api/evaluations/${id}/stop`, { method: "POST" }),
  retryFailedEvaluation: (id: string) =>
    request<EvaluationBatch>(`/api/evaluations/${id}/retry-failed`, {
      method: "POST",
    }),
  reviewEvaluationCase: (
    batchId: string, caseId: string,
    rating: 1 | 2 | 3 | 4 | 5 | null, comment: string,
  ) => request<EvaluationCaseDetail>(
    `/api/evaluations/${batchId}/cases/${caseId}/review`,
    { method: "PUT", body: JSON.stringify({ rating, comment }) },
  ),
  deleteEvaluation: (id: string) =>
    request<{ deleted: string; label: string; conversations: number }>(
      `/api/evaluations/${id}`, { method: "DELETE" },
    ),
  exportEvaluation: (id: string) => download(`/api/evaluations/${id}/export`),
};

async function download(path: string): Promise<Blob> {
  const response = await fetch(path, { credentials: "same-origin" });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(errorDetail(data, response.status));
  }
  return response.blob();
}
