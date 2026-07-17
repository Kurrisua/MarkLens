export type RiskLevel = "low" | "medium" | "high" | "insufficient_evidence";
export type RunStatus = "queued" | "running" | "waiting_for_user" | "completed" | "failed";

export interface DependencyState { status: "ready" | "degraded" | "unavailable"; detail: string }
export interface HealthResponse {
  status: "ok" | "degraded";
  contract_version: string;
  mode: string;
  dependencies: Record<string, DependencyState>;
  data_version: string;
}

export interface AssetResult {
  asset_id: string;
  mime_type: string;
  width: number;
  height: number;
  sha256: string;
  ocr_text: string | null;
  ocr_confidence: number | null;
  ocr_requires_confirmation: boolean;
  phash: string | null;
  created_at: string;
}

export interface CaseContext {
  case_id: string;
  trademark_name: string;
  business_description: string;
  nice_classes: number[];
  image_asset_id: string | null;
  confirmed_ocr_text: string | null;
  facts_snapshot: Record<string, unknown>;
  created_at: string;
}

export interface AgentRun {
  run_id: string;
  agent_type: string;
  status: RunStatus;
  progress: number;
  stage: string;
  resource_type: string | null;
  resource_id: string | null;
  error: { code: string; message: string } | null;
  created_at: string;
  updated_at: string;
}

export interface ScoreBreakdown {
  visual: number | null;
  text: number | null;
  phonetic: number | null;
  semantic: number | null;
  category: number | null;
  overall: number;
  applied_weights: Record<string, number>;
}

export interface TrademarkEvidence {
  hit_id: string;
  rank: number;
  trademark_id: string;
  name: string;
  application_number: string;
  applicant: string;
  nice_classes: number[];
  goods_services: string[];
  status: string;
  status_date: string | null;
  image_asset_id: string | null;
  source_url: string;
  source_name: string;
  source_record_id: string;
  jurisdiction: string;
  is_demo: boolean;
  scores: ScoreBreakdown;
  reasons: string[];
  ocr_evidence: { text: string; confirmed: boolean } | null;
  model_versions: Record<string, string>;
}

export interface EvidenceBundle {
  search_id: string;
  case_id: string;
  status: string;
  query: Record<string, unknown>;
  top_k: number;
  evidence_quality: string;
  methodology: Record<string, unknown> & { weights?: Record<string, number>; notice?: string };
  hits: TrademarkEvidence[];
  created_at: string;
}

export interface Citation {
  citation_id: string;
  source_id: string;
  title: string;
  authority: string;
  locator: string;
  source_url: string;
  excerpt: string;
  effective_from: string;
  effective_to: string | null;
}

export interface RiskAssessment {
  analysis_id: string;
  search_id: string;
  analysis_date: string;
  risk_score: number;
  risk_level: RiskLevel;
  evidence_quality: string;
  applicable_law_version: string;
  methodology: { thresholds?: Record<string, number>; notice?: string; [key: string]: unknown };
  risk_factors: Array<{ title?: string; detail?: string; [key: string]: unknown }>;
  counter_evidence: string[];
  suggestions: string[];
  citations: Citation[];
  uncertainties: string[];
  model_metadata: Record<string, unknown>;
  disclaimer: string;
  created_at: string;
}

export interface DocumentSection { section_id: string; title: string; content: string; citation_ids: string[] }
export interface DocumentDraft {
  document_id: string;
  analysis_id: string;
  document_type: string;
  title: string;
  sections: DocumentSection[];
  citations: Citation[];
  validation_errors: Array<Record<string, unknown>>;
  warnings: string[];
  generation_mode: string;
  can_export: boolean;
  updated_at: string;
}

export interface ConsultationAnswer {
  consultation_id: string;
  question: string;
  answer: string;
  citations: Citation[];
  uncertainties: string[];
  disclaimer: string;
  generation_mode: string;
  created_at: string;
}

export interface SourceDefinition {
  source_key: string;
  name: string;
  adapter_type: string;
  license_name: string;
  license_url: string | null;
  terms_summary: string;
  allowed_domains: string[];
  rate_limit_per_minute: number | null;
  enabled: boolean;
  health: string;
  record_count: number;
  last_synced_at: string | null;
}

export interface IngestionRun {
  ingestion_run_id: string;
  source_key: string;
  status: string;
  fetched_count: number;
  created_count: number;
  updated_count: number;
  skipped_count: number;
  failed_count: number;
  errors: Array<Record<string, unknown>>;
  started_at: string | null;
  finished_at: string | null;
}

export interface Dashboard {
  recent_cases: Array<{ case_id: string; trademark_name: string; nice_classes: number[]; created_at: string }>;
  counts: { trademarks: number; legal_sources: number; cases: number };
  data_version: string;
  legal_version: string;
}
