import type {
  AdminUser, AgentRun, AppDashboard, AssetResult, AuthResponse, CaseContext, CurrentUser, DocumentDraft, ProjectAttachment,
  DocumentSection, EvidenceBundle, LearningArticle, LearningTopic, LearningVideo, OpsOverview, PracticeAttempt,
  PracticeQuestion, OpsPracticeQuestion, Project, ProjectAdvisorMessage, RiskAssessment, SourceDefinition
} from "./contracts";
import { aiSession } from "./ai-session";

export class ApiError extends Error {
  constructor(public code: string, message: string, public requestId?: string) { super(message); }
}

const tokenStorage = typeof localStorage === "undefined" ? null : localStorage;
let accessToken = tokenStorage?.getItem("marklens-access-token") ?? "";
export function setAccessToken(token: string) { accessToken = token; tokenStorage?.setItem("marklens-access-token", token); }
export function clearAccessToken() { accessToken = ""; tokenStorage?.removeItem("marklens-access-token"); }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(path, { ...init, headers, credentials: "include" });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const error = payload?.error;
    throw new ApiError(error?.code ?? "REQUEST_FAILED", error?.message ?? `请求失败：${response.status}`, error?.request_id);
  }
  return payload as T;
}

async function download(path: string, filename: string): Promise<void> {
  const headers = new Headers();
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(path, { headers, credentials: "include" });
  if (!response.ok) throw new ApiError("EXPORT_FAILED", `导出失败：${response.status}`);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url; link.download = filename; link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export const assetUrl = (id: string) => `/api/v1/app/assets/${id}/content`;
export const trademarkImageUrl = (id: string) => `/api/v1/app/trademarks/${id}/image`;

/**
 * <img> cannot attach the in-memory Bearer token used by product APIs. Fetch
 * protected image evidence first, then hand the browser a short-lived blob URL.
 */
export async function protectedImageUrl(path: string): Promise<string> {
  const headers = new Headers();
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(path, { headers, credentials: "include" });
  if (!response.ok) throw new ApiError("IMAGE_LOAD_FAILED", `图样加载失败：${response.status}`);
  return URL.createObjectURL(await response.blob());
}

export const api = {
  register: (input: { email: string; password: string; display_name: string }) => request<AuthResponse>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(input) }),
  login: (input: { email: string; password: string }) => request<AuthResponse>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(input) }),
  refresh: () => request<AuthResponse>("/api/v1/auth/refresh", { method: "POST" }),
  me: () => request<CurrentUser>("/api/v1/auth/me"),
  logout: () => request<void>("/api/v1/auth/logout", { method: "POST" }),
  dashboard: () => request<AppDashboard>("/api/v1/app/dashboard"),
  projects: () => request<Project[]>("/api/v1/app/projects"),
  getProject: (id: string) => request<Project>(`/api/v1/app/projects/${id}`),
  createProject: (input: { name: string; business_description: string }) => request<Project>("/api/v1/app/projects", { method: "POST", body: JSON.stringify(input) }),
  projectMarks: (id: string) => request<CaseContext[]>(`/api/v1/app/projects/${id}/marks`),
  projectAttachments: (id: string) => request<ProjectAttachment[]>(`/api/v1/app/projects/${id}/attachments`),
  uploadProjectAttachment: (projectId: string, file: File) => { const data = new FormData(); data.append("file", file); return request<ProjectAttachment>(`/api/v1/app/projects/${projectId}/attachments`, { method: "POST", body: data }); },
  uploadAsset: (file: File, projectId?: string) => {
    const data = new FormData(); data.append("file", file);
    if (projectId) data.append("project_id", projectId);
    return request<AssetResult>("/api/v1/app/assets", { method: "POST", body: data });
  },
  createMark: (projectId: string, input: { trademark_name: string; business_description: string; nice_classes: number[]; image_asset_id: string | null; confirmed_ocr_text: string | null }) => request<CaseContext>(`/api/v1/app/projects/${projectId}/marks`, { method: "POST", body: JSON.stringify(input) }),
  createSearch: (caseId: string) => request<AgentRun>("/api/v1/app/searches", { method: "POST", headers: aiSession.headers(), body: JSON.stringify({ case_id: caseId, top_k: 10 }) }),
  getSearch: (id: string) => request<EvidenceBundle>(`/api/v1/app/searches/${id}`),
  advisorMessages: (projectId: string) => request<ProjectAdvisorMessage[]>(`/api/v1/app/projects/${projectId}/advisor/messages`),
  askAdvisor: (projectId: string, input: { question: string; case_id: string | null }) => request<AgentRun>(`/api/v1/app/projects/${projectId}/advisor/messages`, { method: "POST", headers: aiSession.headers(), body: JSON.stringify(input) }),
  createRisk: (searchId: string) => request<AgentRun>("/api/v1/app/risk-analyses", { method: "POST", body: JSON.stringify({ search_id: searchId }) }),
  getRisk: (id: string) => request<RiskAssessment>(`/api/v1/app/risk-analyses/${id}`),
  createDocument: (analysisId: string) => request<AgentRun>("/api/v1/app/documents", { method: "POST", body: JSON.stringify({ analysis_id: analysisId, document_type: "trademark_registration_risk_report" }) }),
  savedDocument: (analysisId: string) => request<DocumentDraft>(`/api/v1/app/risk-analyses/${analysisId}/document`),
  getDocument: (id: string) => request<DocumentDraft>(`/api/v1/app/documents/${id}`),
  updateDocument: (id: string, sections: DocumentSection[]) => request<DocumentDraft>(`/api/v1/app/documents/${id}`, { method: "PUT", body: JSON.stringify({ sections }) }),
  exportDocument: (id: string) => download(`/api/v1/app/documents/${id}/export.pdf`, `marklens-report-${id}.pdf`),
  getRun: (id: string) => request<AgentRun>(`/api/v1/app/runs/${id}`),
  topics: () => request<LearningTopic[]>("/api/v1/app/learn/topics"),
  topic: (slug: string) => request<LearningArticle[]>(`/api/v1/app/learn/topics/${slug}`),
  learningVideos: () => request<LearningVideo[]>("/api/v1/app/learn/videos"),
  questions: () => request<PracticeQuestion[]>("/api/v1/app/practice/questions"),
  answerQuestion: (id: string, selected_option: string) => request<PracticeAttempt>(`/api/v1/app/practice/questions/${id}/attempts`, { method: "POST", body: JSON.stringify({ selected_option }) }),
  opsOverview: () => request<OpsOverview>("/api/v1/ops/overview"),
  opsTopics: () => request<LearningTopic[]>("/api/v1/ops/learning/topics"),
  createOpsTopic: (input: { slug: string; title: string; summary: string; body: string; is_published: boolean }) => request<LearningTopic>("/api/v1/ops/learning/topics", { method: "POST", body: JSON.stringify(input) }),
  opsVideos: () => request<LearningVideo[]>("/api/v1/ops/learning/videos"),
  createOpsVideo: (input: { topic_slug: string; title: string; provider: string; external_url: string; duration_label: string; learning_objective: string; is_published: boolean }) => request<LearningVideo>("/api/v1/ops/learning/videos", { method: "POST", body: JSON.stringify(input) }),
  opsQuestions: () => request<OpsPracticeQuestion[]>("/api/v1/ops/practice/questions"),
  createOpsQuestion: (input: { title: string; prompt: string; options: Array<{ id: string; label: string }>; correct_option: string; explanation: string; difficulty: "basic" | "intermediate" | "advanced"; is_published: boolean }) => request<PracticeQuestion>("/api/v1/ops/practice/questions", { method: "POST", body: JSON.stringify(input) }),
  opsRuns: () => request<AgentRun[]>("/api/v1/ops/runs"),
  getSources: () => request<SourceDefinition[]>("/api/v1/ops/sources"),
  syncSource: (key: string) => request<AgentRun>(`/api/v1/ops/sources/${key}/sync`, { method: "POST", body: JSON.stringify({ page_size: 100, max_pages: 100 }) }),
  adminUsers: () => request<AdminUser[]>("/api/v1/admin/users"),
  updateUserRoles: (id: string, roles: string[]) => request<AdminUser>(`/api/v1/admin/users/${id}/roles`, { method: "PUT", body: JSON.stringify({ roles }) })
};
