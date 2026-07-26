import type {
  AgentContent, Conversation, Evidence, PackageInspection, PackageVersion,
  SummaryRun, SummarySkill, WorkflowPlan, WorkflowVersion,
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
    throw new Error(data.detail || `הבקשה נכשלה (${response.status})`);
  }
  return data as T;
}

export const api = {
  conversations: () => request<Conversation[]>("/api/conversations"),
  skills: () => request<SummarySkill[]>("/api/skills"),
  conversation: (id: string) =>
    request<Conversation>(`/api/conversations/${id}`),
  start: (
    rootId: string,
    question: string,
    skillKeys: string[],
    boundaries: GeoJSONMultiPolygon | null = null,
  ) =>
    request<{ conversation: Conversation; run: SummaryRun }>("/api/summaries", {
      method: "POST",
      body: JSON.stringify({
        root_id: rootId,
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
  login: (password: string) =>
    request<{ authenticated: boolean }>("/api/admin/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),
  logout: () => request("/api/admin/session", { method: "DELETE" }),
  settings: () => request<Record<string, unknown>>("/api/settings"),
  models: () => request<{ models: string[] }>("/api/models"),
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
  workflows: () => request<WorkflowVersion[]>("/api/workflows"),
  createWorkflow: (data: Record<string, unknown>) =>
    request<WorkflowVersion>("/api/workflows", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  planWorkflow: (prompt: string) =>
    request<WorkflowPlan>("/api/workflows/plan", {
      method: "POST",
      body: JSON.stringify({ prompt }),
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
  reviewQueue: () => request<Array<Record<string, unknown>>>("/api/review-queue"),
};
