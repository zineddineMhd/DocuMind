export interface User { id: string; email: string; name: string; created_at: string }

export interface Workspace {
  id: string; name: string; created_at: string; document_count: number; conversation_count: number;
}

export type DocStatus = "pending" | "processing" | "ready" | "failed";

export interface Doc {
  id: string; workspace_id: string; filename: string; content_type: string; file_size: number;
  page_count: number | null; chunk_count: number; status: DocStatus; error: string | null;
  summary: string | null; keywords: string[] | null; created_at: string;
}

export interface Source {
  source_id: string; document_id: string | null; filename: string; page: number | null;
  section?: string | null; chunk_id: string; excerpt: string; available: boolean;
}

export type AnswerStatus = "answered" | "no_answer" | "uncertain" | "error";
export type ChatMode = "qa" | "summary" | "compare" | "explain";

export interface ChatMessage {
  id: string; role: "user" | "assistant"; content: string; status: AnswerStatus | null;
  feedback: number | null; sources: Source[]; created_at: string; streaming?: boolean;
  metrics?: Record<string, unknown> | null;
}

export interface Conversation {
  id: string; workspace_id: string; title: string; created_at: string; updated_at: string; message_count: number;
}

export interface ChatFinal {
  conversation_id: string; message_id: string; answer: string; sources: Source[];
  status: AnswerStatus; created_at: string; metrics: Record<string, unknown>;
}

export interface Chunk { id: string; page: number | null; section: string | null; ordinal: number; text: string }

export interface SearchResult {
  chunk_id: string; document_id: string; filename: string; page: number | null; section: string | null;
  text: string; score: number; similarity: number | null;
}

export interface Stats {
  workspaces: number; documents: number; documents_by_status: Record<string, number>; conversations: number;
  questions: number; abstention_rate: number; storage_used: number; storage_quota: number;
  config: {
    gemini_model: string; gemini_configured: boolean; embedding_version: string; hybrid_search: boolean;
    reranker: string | null; max_upload_mb: number; top_k: number; chunk_size: number; rate_limit_chat_per_min: number;
  };
}
