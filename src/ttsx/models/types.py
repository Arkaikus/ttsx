"""Type definitions for models.

This module uses huggingface_hub.hf_api.ModelInfo directly instead of duplicating it.
We only define helper functions and our own domain-specific models.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from huggingface_hub import get_paths_info
from huggingface_hub.hf_api import ModelInfo  # Use upstream type
from pydantic import BaseModel, Field, computed_field

logger = logging.getLogger(__name__)


# Export ModelInfo from huggingface_hub for convenience
__all__ = [
    "ModelInfo",
    "InstalledModel",
    "get_model_size",
    "get_model_size_async",
    "format_model_size",
]


def get_model_size(model: ModelInfo, fetch_accurate: bool = True) -> Optional[int]:
    """Get model size in bytes from HuggingFace ModelInfo.
    
    Args:
        model: HuggingFace ModelInfo object
        fetch_accurate: If True, query HF API for accurate sizes (slower but accurate).
                       If False, only use cached sibling data (fast but often None).
        
    Returns:
        Total size in bytes, or None if not available
    """
    # First try siblings (fast but often None for size field)
    if hasattr(model, "siblings") and model.siblings:
        try:
            sizes_from_siblings = [
                getattr(sibling, "size", 0) or 0 
                for sibling in model.siblings
            ]
            if any(sizes_from_siblings):
                total = sum(sizes_from_siblings)
                if total > 0:
                    return total
        except Exception as e:
            logger.debug(f"Failed to get size from siblings: {e}")
    
    # If fetch_accurate is True, query actual file sizes from HF API
    if fetch_accurate:
        try:
            from huggingface_hub import HfApi
            
            logger.debug(f"Fetching accurate size for {model.id}")
            
            # Step 1: Get list of all files in the repo
            api = HfApi()
            all_files = api.list_repo_files(repo_id=model.id, repo_type="model")
            
            # Step 2: Filter for model weight files (these are the large ones)
            model_files = [
                f for f in all_files 
                if f.endswith(('.safetensors', '.bin', '.pt', '.pth', '.ckpt'))
            ]
            
            if not model_files:
                logger.debug(f"No model weight files found for {model.id}")
                return None
            
            # Step 3: Get accurate sizes for those files
            paths_info = list(get_paths_info(
                repo_id=model.id,
                paths=model_files,
                repo_type="model",
            ))
            
            total_size = sum(info.size for info in paths_info if info.size)
            
            if total_size > 0:
                logger.debug(f"Got accurate size for {model.id}: {total_size / 1024**3:.2f} GB")
                return total_size
                
        except Exception as e:
            logger.warning(f"Failed to fetch accurate size for {model.id}: {e}")
    
    return None


async def get_model_size_async(model: ModelInfo) -> Optional[int]:
    """Async version of get_model_size for concurrent fetching.
    
    Args:
        model: HuggingFace ModelInfo object
        
    Returns:
        Total size in bytes, or None if not available
    """
    loop = asyncio.get_event_loop()
    # Run the blocking I/O operation in a thread pool
    return await loop.run_in_executor(
        None, lambda: get_model_size(model, fetch_accurate=True)
    )


def format_model_size(size_bytes: Optional[int]) -> str:
    """Format model size as human-readable string.
    
    Args:
        size_bytes: Size in bytes, or None
        
    Returns:
        Formatted string like "3.4 GB", "120 MB", or "Unknown"
    """
    if size_bytes is None:
        return "Unknown"
    
    # GB
    gb = size_bytes / (1024**3)
    if gb >= 1:
        return f"{gb:.1f} GB"
    
    # MB
    mb = size_bytes / (1024**2)
    if mb >= 1:
        return f"{mb:.0f} MB"
    
    # KB
    kb = size_bytes / 1024
    if kb >= 1:
        return f"{kb:.0f} KB"
    
    # Bytes
    return f"{size_bytes} B"


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
