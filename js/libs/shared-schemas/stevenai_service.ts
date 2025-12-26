/**
 * StevenAI Service API schemas.
 * Type-safe contracts for stevenai-service endpoints.
 *
 * This file mirrors the Python schemas in:
 * python/libs/shared-schemas/shared_schemas/stevenai_service.py
 */

// ============================================================================
// Chat Response Types
// ============================================================================

/**
 * Types of chat response chunks in SSE stream.
 */
export enum ChatChunkType {
  DELTA = "delta",      // Streaming text delta
  CONTEXT = "context",  // RAG contexts
  DONE = "done",        // Stream complete
  ERROR = "error"       // Error occurred
}

// ============================================================================
// Chat Request/Response
// ============================================================================

/**
 * Request for chat completion with streaming.
 */
export interface ChatRequest {
  /** Current user question */
  query: string;
  /** Previous question (for follow-up rewriting) */
  last_q?: string | null;
  /** Previous answer (for follow-up rewriting) */
  last_a?: string | null;
  /** Model to use: 'chatGPT' for OpenAI, or exact GPU model ID (e.g., 'Qwen/Qwen2.5-7B-Instruct') */
  model?: string;
  /** Include RAG documents dataset */
  use_docs_of_fact?: boolean;
  /** Include RAG QA pairs dataset */
  use_qa_pairs?: boolean;
  /** Sampling temperature (0.0-2.0) */
  temperature?: number;
  /** Maximum tokens to generate (1-4096) */
  max_tokens?: number;
  /** Enable streaming (required) */
  stream?: boolean;
}

/**
 * Retrieved RAG context document.
 */
export interface RAGContext {
  content: string;
  score: number;
  metadata: Record<string, any>;
}

/**
 * Single SSE chunk for streaming response.
 */
export interface ChatResponseChunk {
  type: ChatChunkType;
  /** Text delta (for type="delta") */
  delta?: string | null;
  /** Complete text (for type="done") */
  full_text?: string | null;
  /** RAG contexts (for type="context") */
  contexts?: RAGContext[] | null;
  /** Error message (for type="error") */
  error?: string | null;
}

/**
 * Complete chat response (final message).
 */
export interface ChatResponse {
  answer: string;
  model_used: string;
  contexts: RAGContext[];
}

// ============================================================================
// Health Check
// ============================================================================

/**
 * Health check response.
 */
export interface HealthResponse {
  /** "healthy", "degraded", or "unhealthy" */
  status: string;
  service: string;
  version: string;
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard to check if a chunk is a delta chunk.
 */
export function isDeltaChunk(chunk: ChatResponseChunk): chunk is ChatResponseChunk & { delta: string } {
  return chunk.type === ChatChunkType.DELTA && typeof chunk.delta === 'string';
}

/**
 * Type guard to check if a chunk is a context chunk.
 */
export function isContextChunk(chunk: ChatResponseChunk): chunk is ChatResponseChunk & { contexts: RAGContext[] } {
  return chunk.type === ChatChunkType.CONTEXT && Array.isArray(chunk.contexts);
}

/**
 * Type guard to check if a chunk is a done chunk.
 */
export function isDoneChunk(chunk: ChatResponseChunk): chunk is ChatResponseChunk & { full_text: string } {
  return chunk.type === ChatChunkType.DONE && typeof chunk.full_text === 'string';
}

/**
 * Type guard to check if a chunk is an error chunk.
 */
export function isErrorChunk(chunk: ChatResponseChunk): chunk is ChatResponseChunk & { error: string } {
  return chunk.type === ChatChunkType.ERROR && typeof chunk.error === 'string';
}

// ============================================================================
// Default Values
// ============================================================================

/**
 * Default values for ChatRequest to match Python defaults.
 */
export const DEFAULT_CHAT_REQUEST: Partial<ChatRequest> = {
  model: "chatGPT",
  use_docs_of_fact: false,
  use_qa_pairs: false,
  temperature: 0.7,
  max_tokens: 2048,
  stream: true
};

/**
 * Helper to create a ChatRequest with defaults.
 */
export function createChatRequest(partial: Partial<ChatRequest> & { query: string }): ChatRequest {
  return {
    ...DEFAULT_CHAT_REQUEST,
    ...partial
  } as ChatRequest;
}
