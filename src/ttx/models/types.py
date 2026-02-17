"""Type definitions for models."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ModelInfo:
    """Information about a TTS model."""

    model_id: str
    author: str
    name: str
    downloads: int
    likes: int
    last_modified: datetime
    tags: list[str]
    pipeline_tag: str
    library_name: Optional[str] = None
    size_bytes: Optional[int] = None
    description: Optional[str] = None

    @property
    def full_name(self) -> str:
        """Get the full model name (author/name)."""
        return self.model_id

    @property
    def short_name(self) -> str:
        """Get just the model name without author."""
        return self.name

    @property
    def size_mb(self) -> Optional[float]:
        """Get model size in megabytes."""
        if self.size_bytes:
            return self.size_bytes / (1024 * 1024)
        return None

    @property
    def size_gb(self) -> Optional[float]:
        """Get model size in gigabytes."""
        if self.size_bytes:
            return self.size_bytes / (1024 * 1024 * 1024)
        return None


@dataclass
class InstalledModel:
    """Information about an installed model."""

    model_id: str
    path: Path
    installed_at: datetime
    size_bytes: int
    last_used: Optional[datetime] = None
    is_pinned: bool = False

    @property
    def size_mb(self) -> float:
        """Get model size in megabytes."""
        return self.size_bytes / (1024 * 1024)

    @property
    def size_gb(self) -> float:
        """Get model size in gigabytes."""
        return self.size_bytes / (1024 * 1024 * 1024)
