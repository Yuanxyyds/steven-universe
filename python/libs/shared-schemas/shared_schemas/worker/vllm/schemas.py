"""
vLLM Worker Schemas

Shared schemas for GPU service <-> vLLM worker communication.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


# ============================================================================
# Task Request (Worker-Specific)
# ============================================================================

class VLLMTaskRequest(BaseModel):
    """
    Task request sent from GPU service to vLLM worker.

    Sent via: POST /task
    """
    task_id: str = Field(..., description="Unique task identifier")
    model_id: str = Field(..., description="Model identifier (e.g., Qwen/Qwen2.5-7B-Instruct)")

    # Chat messages (primary interface)
    messages: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Chat messages in OpenAI format: [{'role': 'user', 'content': '...'}]"
    )

    # Raw prompt (alternative interface)
    prompt: Optional[str] = Field(
        default=None,
        description="Raw prompt text (alternative to messages)"
    )

    # Generation parameters (OpenAI-compatible)
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature"
    )
    max_tokens: int = Field(
        default=512,
        ge=1,
        le=4096,
        description="Maximum tokens to generate"
    )
    top_p: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling top-p"
    )
    top_k: int = Field(
        default=-1,
        description="Top-k sampling (-1 disables)"
    )
    stream: bool = Field(
        default=True,
        description="Stream response tokens"
    )
    stop: Optional[List[str]] = Field(
        default=None,
        description="Stop sequences"
    )

    # Additional metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Task-specific parameters"
    )

    def get_prompt_or_messages(self) -> tuple[Optional[str], Optional[List[Dict[str, str]]]]:
        """Return (prompt, messages) - exactly one should be non-None."""
        if self.messages:
            return None, self.messages
        elif self.prompt:
            return self.prompt, None
        else:
            # Default fallback
            return "Hello!", None


# ============================================================================
# Status Response (Optional)
# ============================================================================

class VLLMStatusResponse(BaseModel):
    """
    vLLM worker detailed status (optional endpoint).

    Returned from: GET /status
    """
    status: str = Field(..., description="Worker status: ready, loading, busy")
    model_loaded: str = Field(..., description="Currently loaded model")
    vllm_status: str = Field(..., description="vLLM server health status")
