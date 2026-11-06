export interface HealthStatus {
  status: "ok" | "degraded";
  database: boolean;
  pgvector: boolean;
}

export type DocumentStatus = "uploaded" | "processing" | "extracting" | "embedding" | "ready" | "failed";

export interface FinDocument {
  id: string;
  filename: string;
  title: string | null;
  company: string | null;
  report_type: string | null;
  fiscal_year: string | null;
  page_count: number | null;
  status: DocumentStatus;
  error: string | null;
  created_at: string;
}

export interface DocumentList {
  items: FinDocument[];
  total: number;
  page: number;
  page_size: number;
}

export interface TableSummary {
  id: string;
  page_number: number;
  table_type: string | null;
  title: string | null;
  markdown: string | null;
}

export interface DocumentDetail extends FinDocument {
  tables: TableSummary[];
  chunk_count: number;
}

export interface SearchHit {
  chunk_id: string;
  document_id: string;
  document_name: string;
  page_number: number;
  section: string | null;
  content: string;
  kind: string;
  similarity: number | null;
  score: number;
  matched_by: string[];
}

export interface SearchResponse {
  query: string;
  hits: SearchHit[];
}

export interface ChatSource {
  label: number;
  document_id: string;
  document_name: string;
  page_number: number;
  section: string | null;
  chunk_id: string | null;
  score: number | null;
  snippet: string | null;
}

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  answer: string;
  sources: ChatSource[];
  refused: boolean;
  tool_used?: string | null;
  rewritten_question: string | null;
}

export interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  refused?: boolean;
  tool_used?: string | null;
}
