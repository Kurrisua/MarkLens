import type {
  AgentRun, AssetResult, CaseContext, ConsultationAnswer, Dashboard, DocumentDraft,
  DocumentSection, EvidenceBundle, HealthResponse, IngestionRun, RiskAssessment, SourceDefinition
} from "./contracts";

export class ApiError extends Error {
  constructor(public code: string, message: string, public requestId?: string) { super(message); }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...init, headers });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const error = payload?.error;
    throw new ApiError(error?.code ?? "REQUEST_FAILED", error?.message ?? `请求失败：${response.status}`, error?.request_id);
  }
  return payload as T;
}

export const assetUrl = (id: string) => `/api/v1/assets/${id}/content`;

export const api = {
  health: () => request<HealthResponse>("/health"),
  dashboard: () => request<Dashboard>("/api/v1/dashboard"),
  uploadAsset: (file: File) => {
    const data = new FormData(); data.append("file", file);
    return request<AssetResult>("/api/v1/assets", { method: "POST", body: data });
  },
  createCase: (input: { trademark_name: string; business_description: string; nice_classes: number[]; image_asset_id: string | null; confirmed_ocr_text: string | null }) =>
    request<CaseContext>("/api/v1/cases", { method: "POST", body: JSON.stringify(input) }),
  createSearch: (caseId: string) => request<AgentRun>("/api/v1/searches", { method: "POST", body: JSON.stringify({ case_id: caseId, top_k: 10 }) }),
  getSearch: (id: string) => request<EvidenceBundle>(`/api/v1/searches/${id}`),
  createRisk: (searchId: string) => request<AgentRun>("/api/v1/risk-analyses", { method: "POST", body: JSON.stringify({ search_id: searchId }) }),
  getRisk: (id: string) => request<RiskAssessment>(`/api/v1/risk-analyses/${id}`),
  createDocument: (analysisId: string) => request<AgentRun>("/api/v1/documents", { method: "POST", body: JSON.stringify({ analysis_id: analysisId, document_type: "trademark_registration_risk_report" }) }),
  getDocument: (id: string) => request<DocumentDraft>(`/api/v1/documents/${id}`),
  updateDocument: (id: string, sections: DocumentSection[]) => request<DocumentDraft>(`/api/v1/documents/${id}`, { method: "PUT", body: JSON.stringify({ sections }) }),
  validateDocument: (id: string) => request<DocumentDraft>(`/api/v1/documents/${id}/validate`, { method: "POST" }),
  createConsultation: (question: string) => request<AgentRun>("/api/v1/consultations", { method: "POST", body: JSON.stringify({ question }) }),
  getConsultation: (id: string) => request<ConsultationAnswer>(`/api/v1/consultations/${id}`),
  getRun: (id: string) => request<AgentRun>(`/api/v1/agent-runs/${id}`),
  getSources: () => request<SourceDefinition[]>("/api/v1/sources"),
  syncSource: (key: string) => request<AgentRun>(`/api/v1/sources/${key}/sync`, { method: "POST", body: JSON.stringify({ page_size: 100, max_pages: 100 }) }),
  getIngestion: (id: string) => request<IngestionRun>(`/api/v1/ingestion-runs/${id}`)
};
