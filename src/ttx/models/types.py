"""Type definitions for models using Pydantic."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class ModelInfo(BaseModel):
    """Information about a TTS model from HuggingFace Hub.
    
    Uses Pydantic for validation and serialization.
    """

    model_id: str = Field(..., description="Full model ID (author/model-name)")
    author: str = Field(..., description="Model author/organization")
    name: str = Field(..., description="Model name without author")
    downloads: int = Field(default=0, ge=0, description="Total downloads")
    likes: int = Field(default=0, ge=0, description="Number of likes")
    last_modified: datetime = Field(..., description="Last modification date")
    tags: list[str] = Field(default_factory=list, description="Model tags")
    pipeline_tag: str = Field(default="text-to-speech", description="Pipeline task type")
    library_name: Optional[str] = Field(None, description="ML library (pytorch, etc)")
    size_bytes: Optional[int] = Field(None, ge=0, description="Model size in bytes")
    description: Optional[str] = Field(None, description="Model description")

    model_config = {"frozen": False}

    @computed_field  # type: ignore[misc]
    @property
    def full_name(self) -> str:
        """Get the full model name (author/name)."""
        return self.model_id

    @computed_field  # type: ignore[misc]
    @property
    def short_name(self) -> str:
        """Get just the model name without author."""
        return self.name

    @computed_field  # type: ignore[misc]
    @property
    def size_mb(self) -> Optional[float]:
        """Get model size in megabytes."""
        if self.size_bytes:
            return self.size_bytes / (1024 * 1024)
        return None

    @computed_field  # type: ignore[misc]
    @property
    def size_gb(self) -> Optional[float]:
        """Get model size in gigabytes."""
        if self.size_bytes:
            return self.size_bytes / (1024 * 1024 * 1024)
        return None
    
    def format_size(self) -> str:
        """Format size as human-readable string."""
        if self.size_bytes is None:
            return "Unknown"
        
        gb = self.size_gb
        if gb and gb >= 1:
            return f"{gb:.1f} GB"
        
        mb = self.size_mb
        if mb and mb >= 1:
            return f"{mb:.0f} MB"
        
        return f"{self.size_bytes} B"


class InstalledModel(BaseModel):
    """Information about a locally installed model.
    
    Uses Pydantic for validation and JSON serialization.
    """

    model_id: str = Field(..., description="Full model ID")
    path: Path = Field(..., description="Local path to model")
    installed_at: datetime = Field(..., description="Installation timestamp")
    size_bytes: int = Field(..., ge=0, description="Model size in bytes")
    last_used: Optional[datetime] = Field(None, description="Last usage timestamp")
    is_pinned: bool = Field(default=False, description="Whether model is pinned")

    model_config = {"frozen": False, "arbitrary_types_allowed": True}

    @computed_field  # type: ignore[misc]
    @property
    def size_mb(self) -> float:
        """Get model size in megabytes."""
        return self.size_bytes / (1024 * 1024)

    @computed_field  # type: ignore[misc]
    @property
    def size_gb(self) -> float:
        """Get model size in gigabytes."""
        return self.size_bytes / (1024 * 1024 * 1024)
