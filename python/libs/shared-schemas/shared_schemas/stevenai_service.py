"""
StevenAI Service API schemas.
Type-safe contracts for stevenai-service endpoints.
"""

from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


# ============================================================================
# Chat Response Types
# ============================================================================

class ChatChunkType(str, Enum):
    """Types of chat response chunks in SSE stream."""
    DELTA = "delta"      # Streaming text delta
    CONTEXT = "context"  # RAG contexts
    DONE = "done"        # Stream complete
    ERROR = "error"      # Error occurred


# ============================================================================
# Chat Request/Response
# ============================================================================

class ChatRequest(BaseModel):
    """Request for chat completion with streaming."""
    query: str = Field(..., description="Current user question")
    last_q: Optional[str] = Field(default=None, description="Previous question (for follow-up rewriting)")
    last_a: Optional[str] = Field(default=None, description="Previous answer (for follow-up rewriting)")
    model: str = Field(
        default="chatGPT",
        description="Model to use: 'chatGPT' for OpenAI, or exact GPU model ID (e.g., 'Qwen/Qwen2.5-7B-Instruct')"
    )
    use_docs_of_fact: bool = Field(
        default=False,
        description="Include RAG documents dataset"
    )
    use_qa_pairs: bool = Field(
        default=False,
        description="Include RAG QA pairs dataset"
    )
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=2048, ge=1, le=4096)
    stream: bool = Field(default=True, description="Enable streaming (required)")


class RAGContext(BaseModel):
    """Retrieved RAG context document."""
    content: str
    score: float
    metadata: Dict[str, Any]


class ChatResponseChunk(BaseModel):
    """Single SSE chunk for streaming response."""
    type: ChatChunkType
    delta: Optional[str] = None          # For type="delta"
    full_text: Optional[str] = None      # For type="done"
    contexts: Optional[List[RAGContext]] = None  # For type="context"
    error: Optional[str] = None          # For type="error"


class ChatResponse(BaseModel):
    """Complete chat response (final message)."""
    answer: str
    model_used: str
    contexts: List[RAGContext]


# ============================================================================
# Health Check
# ============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str  # "healthy", "degraded", "unhealthy"
    service: str
    version: str
