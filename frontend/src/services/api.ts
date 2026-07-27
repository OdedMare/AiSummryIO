import type {
  AgentContent, Conversation, Evidence, PackageInspection, PackageVersion,
  PlanChatMessage, SkillPreviewResult, SummaryRun, SummarySkill,
  ToolPlanChatTurn, ToolPlanDraft, WorkflowPlan, WorkflowPlanChatTurn,
  WorkflowVersion,
} from "@/types";
import type { GeoJSONMultiPolygon } from "@/types/geo";

export async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    credentials: "same-origin",
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(errorDetail(data, response.status));
  }
  return data as T;
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

export const api = {
  conversations: () => request<Conversation[]>("/api/conversations"),
  skills: () => request<SummarySkill[]>("/api/skills"),
  conversation: (id: string) =>
    request<Conversation>(`/api/conversations/${id}`),
  // Either rootId or boundaries must be present; the backend rejects a
  // request carrying neither.
  start: (
    rootId: string,
    question: string,
    skillKeys: string[],
    boundaries: GeoJSONMultiPolygon | null = null,
  ) =>
    request<{ conversation: Conversation; run: SummaryRun }>("/api/summaries", {
      method: "POST",
      body: JSON.stringify({
        root_id: rootId || null,
        question,
        skill_keys: skillKeys,
        boundaries,
      }),
    }),
  followUp: (
    conversationId: string,
    question: string,
    skillKeys: string[],
  ) =>
    request<SummaryRun>(`/api/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({ question, skill_keys: skillKeys }),
    }),
  run: (id: string) => request<SummaryRun>(`/api/runs/${id}`),
  evidence: (id: string) => request<Evidence[]>(`/api/runs/${id}/evidence`),
  feedback: (runId: string, rating: -1 | 1, comment = "") =>
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
  packages: () => request<PackageVersion[]>("/api/packages"),
  createPackage: (data: Record<string, unknown>) =>
    request<PackageVersion>("/api/packages", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  inspectPackage: (data: Record<string, unknown>) =>
    request<PackageInspection>("/api/packages/inspect", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  planToolChat: (
    messages: PlanChatMessage[], draft: Partial<ToolPlanDraft>,
    inspection: PackageInspection | null,
  ) =>
    request<ToolPlanChatTurn>("/api/packages/plan-chat", {
      method: "POST",
      body: JSON.stringify({ messages, draft, inspection: inspection ?? {} }),
    }),
  workflows: () => request<WorkflowVersion[]>("/api/workflows"),
  createWorkflow: (data: Record<string, unknown>) =>
    request<WorkflowVersion>("/api/workflows", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  planWorkflowChat: (
    messages: PlanChatMessage[], draft: WorkflowPlan | null,
  ) =>
    request<WorkflowPlanChatTurn>("/api/workflows/plan-chat", {
      method: "POST",
      body: JSON.stringify({ messages, draft: draft ?? {} }),
    }),
  publishWorkflow: (id: string) =>
    request<WorkflowVersion>(`/api/workflows/${id}/publish`, { method: "POST" }),
  dryRun: (id: string, rootId: string) =>
    request<Record<string, unknown>>(`/api/workflows/${id}/dry-run`, {
      method: "POST",
      body: JSON.stringify({ root_id: rootId, question: "בדיקת FDE" }),
    }),
  content: () => request<AgentContent[]>("/api/agent-content"),
  createContent: (data: Record<string, unknown>) =>
    request<AgentContent>("/api/agent-content", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  publishContent: (id: string) =>
    request<AgentContent>(`/api/agent-content/${id}/publish`, { method: "POST" }),
  previewSkill: (data: Record<string, unknown>) =>
    request<SkillPreviewResult>("/api/agent-content/preview-skill", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  reviewQueue: () => request<Array<Record<string, unknown>>>("/api/review-queue"),
};
