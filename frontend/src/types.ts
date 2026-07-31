export type ChatRole = "user" | "assistant";

export type ChatHistoryMessage = {
  role: ChatRole;
  content: string;
};

export type ChatContinuation = {
  has_more?: boolean;
  mode: "broad_section";
  document_id: string;
  section_root: string;
  next_offset: number;
  source_question: string;
  token: string;
};

export type ChatFilters = {
  document_ids?: string[];
  include_parent_chunks?: boolean;
  document_scope?: "all" | "selected";
};

export type Citation = {
  citation_id: string;
  document_name: string;
  section: string;
  chunk_id: string;
  excerpt: string;
  images: Array<{
    url?: string;
    file_name?: string;
    anchor_text?: string;
  }>;
  content?: string;
  content_blocks?: CitationBlock[];
};

export type CitationBlock = {
  text: string;
  images: Array<{
    url?: string;
    file_name?: string;
    anchor_text?: string;
  }>;
};

export type ChatResponse = {
  status:
    | "answered"
    | "partial"
    | "insufficient_context"
    | "out_of_scope"
    | "conversational"
    | "clarify"
    | "generation_failed"
    | "conflict";
  answer: string;
  citations: Citation[];
  retrieval: {
    candidate_count: number;
    context_count: number;
    reranker_used: boolean;
  };
  timing_ms: Record<string, number>;
  continuation?: ChatContinuation | null;
  trace?: RouteTrace | null;
};

export type ChatStreamEvent =
  | {
      event: "progress";
      data: {
        stage: string;
        message: string;
      };
    }
  | {
      event: "delta";
      data: {
        text: string;
      };
    }
  | {
      event: "final";
      data: ChatResponse;
    }
  | {
      event: "error";
      data: {
        message: string;
        detail?: string;
      };
    };

export type RouteTrace = {
  intent?: string | null;
  subtype?: string | null;
  confidence?: number | null;
  reason?: string | null;
  branch?: string | null;
  candidate_count?: number | null;
  context_count?: number | null;
  best_score?: number | null;
  parse_error?: string | null;
  literal_validation_error?: string | null;
  /** @deprecated RAG V2 no longer runs the heuristic fact guard. */
  fact_guard_error?: string | null;
  rewrite_used?: boolean;
  llm_router_used?: boolean;
  retrieval_first?: boolean;
  adaptive_rewrite_used?: boolean;
  adaptive_rewrite_error?: string | null;
  retrieval_queries?: string[];
  candidate_quality?: string | null;
  selected_chunk_ids?: string[];
  rejected_chunks?: Record<string, string>;
};

export type DocumentRecord = {
  document_id: string;
  original_name: string;
  status: string;
  chunk_count: number;
  parent_chunks: number;
  child_chunks: number;
  image_count: number;
  vector_index_status: string;
  created_at: string;
};

export type AppMessage = {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: Date;
  status?: ChatResponse["status"] | "error";
  citations?: Citation[];
  retrieval?: ChatResponse["retrieval"];
  timing_ms?: ChatResponse["timing_ms"];
  trace?: RouteTrace | null;
};
