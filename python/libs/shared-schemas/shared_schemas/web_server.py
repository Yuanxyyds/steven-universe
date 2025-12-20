"""
Web Server API schemas.
Type-safe contracts for all web-server endpoints.
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field


# ============================================================================
# Health Check
# ============================================================================
class HealthResponse(BaseModel):
    """Health check response."""
    status: str  # "healthy", "degraded", "unhealthy"
    version: str

# ============================================================================
# LandSink Prediction
# ============================================================================

class LandsinkPredictionRequest(BaseModel):
    """Request for landsink prediction."""
    year: int = Field(default=2023, ge=1900, le=2200)


class LandsinkPredictionResponse(BaseModel):
    """Response with landsink prediction."""
    success: bool
    year: int
    predicted_temperature: float
    predicted_sea_level: float
    map_html: str  # HTML content for interactive map


# ============================================================================
# Food Classification
# ============================================================================

class FoodPrediction(BaseModel):
    """Single prediction from a model."""
    label: str
    confidence: float


class ModelPredictions(BaseModel):
    """Predictions from a single model."""
    model_name: str
    top_predictions: List[FoodPrediction]


class FoodClassificationResponse(BaseModel):
    """Response with food classification results."""
    success: bool
    predictions: List[ModelPredictions]  # Results from multiple models


# ============================================================================
# AI Chat
# ============================================================================

class ChatQueryRequest(BaseModel):
    """Request to query AI chatbot."""
    q: str = Field(..., description="User question")
    model: str = Field(default="gpt4o", description="Model to use (gpt4o, llama)")
    context: str = Field(default="qa-docs", description="Context source (qa, docs, qa-docs)")
    last_q: Optional[str] = Field(default=None, description="Previous question for follow-up")
    last_a: Optional[str] = Field(default=None, description="Previous answer for follow-up")


class ChatContextSource(BaseModel):
    """Source of context used in response."""
    type: str  # "qa" or "doc"
    content: str
    metadata: Optional[dict] = None


class ChatQueryResponse(BaseModel):
    """Response from AI chatbot."""
    success: bool
    answer: str
    model_used: str
    context_used: List[ChatContextSource]
    is_follow_up: bool


# ============================================================================
# Unified Status (Combines Health + Stats)
# ============================================================================

class ServiceInfo(BaseModel):
    """Information about a service running on a node."""
    name: str
    online: bool
    response_time_ms: Optional[float] = None


class NodeInfo(BaseModel):
    """Information about a node within a server."""
    name: str
    online: bool
    # Proxmox node stats (optional, only if available)
    memory_used_gb: Optional[float] = None
    memory_total_gb: Optional[float] = None
    memory_usage_percent: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    cpu_cores: Optional[int] = None
    cpu_temp_celsius: Optional[float] = None
    # Services running on this node
    services: Dict[str, ServiceInfo] = Field(default_factory=dict)


class ServerInfo(BaseModel):
    """Information about a server (e.g., Proxmox host)."""
    name: str
    online: bool
    # Nodes within this server
    nodes: Dict[str, NodeInfo] = Field(default_factory=dict)


class UnifiedStatusResponse(BaseModel):
    """Unified status response combining health and stats."""
    status: str  # "healthy", "degraded", "unhealthy"
    servers: Dict[str, ServerInfo]
