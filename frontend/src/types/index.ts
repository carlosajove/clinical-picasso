export interface CorpusStats {
  total_documents: number;
  by_type: Record<string, number>;
  by_format: Record<string, number>;
  by_country: Record<string, number>;
  by_therapeutic_area: Record<string, number>;
  by_phase: Record<string, number>;
  interventions: string[];
  trial_count: number;
  document_classes: number;
  file_formats: number;
  countries: number;
  therapeutic_areas: number;
}

export interface DocumentSummary {
  doc_id: string;
  filename: string;
  document_type: string;
  confidence: number;
  version: string | null;
  country: string | null;
  site_id: string | null;
  sponsor_protocol_id: string | null;
  sponsor_name: string | null;
  trial_title: string | null;
  intervention: string | null;
  indication: string | null;
  therapeutic_area: string | null;
  phase: string | null;
  summary: string | null;
  references_to: string[];
  raw_sha256: string;
}

export interface DocumentDetail extends DocumentSummary {
  classes: { class_name: string; confidence: number; reasoning: string }[];
}

export interface GraphNode {
  type: string; // "node"
  label: string; // "Document" | "Trial"
  id: string;
  data: Record<string, unknown>;
}

export interface GraphEdge {
  type: string; // "edge"
  label: string; // "Supersedes" | "DerivedFrom" etc
  source: string;
  target: string;
  data?: Record<string, unknown>;
}

export interface CascadeResult {
  source_doc_id: string;
  derived: Record<string, unknown>[];
  references: Record<string, unknown>[];
  governed: Record<string, unknown>[];
  total_affected: number;
}

export interface AuditReport {
  total_issues: number;
  errors: number;
  warnings: number;
  by_category: Record<string, AuditIssue[]>;
}

export interface AuditIssue {
  severity: 'error' | 'warning' | 'info';
  doc_id: string | null;
  description: string;
  details: Record<string, unknown>;
}

export interface ChatResponse {
  question: string;
  gq_query: string;
  explanation: string;
  rows: Record<string, unknown>[];
  error: string | null;
}

export interface IngestStep {
  step: string;
  status: 'running' | 'done' | 'error';
  cached?: boolean;
  error?: string;
}

export interface IngestClassification {
  document_type: string;
  confidence: number;
  trial: string | null;
  version: string | null;
}

export interface IngestResult {
  doc_id: string;
  document_type: string;
  trial_key: string | null;
  is_orphan: boolean;
  changes: { action: string; target_type: string; details: Record<string, unknown> }[];
}
