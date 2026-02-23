"""Cache management for TTS models."""

import logging
import shutil
from pathlib import Path
from typing import Any

from ttsx.config import get_config
from ttsx.models.registry import ModelRegistry
from ttsx.utils.exceptions import CacheError

logger = logging.getLogger(__name__)


class CacheManager:
    """Manage model cache with size limits and LRU eviction."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        max_size_gb: int | None = None,
        registry: ModelRegistry | None = None,
    ) -> None:
        """Initialize the cache manager.

        Args:
            cache_dir: Cache directory. Uses config default if None.
            max_size_gb: Maximum cache size in gigabytes. Uses config default if None.
            registry: Model registry. Creates new one if None.
        """
        config = get_config()
        self.cache_dir = cache_dir or config.models_cache_path
        self.max_size_gb = max_size_gb or config.max_cache_size_gb
        self.max_size_bytes = self.max_size_gb * 1024 * 1024 * 1024
        self.registry = registry or ModelRegistry()

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_size(self) -> int:
        """Get current cache size in bytes.

        Returns:
            Cache size in bytes.
        """
        return self.registry.get_total_size()

    def get_available_space(self) -> int:
        """Get available space in the cache.

        Returns:
            Available space in bytes.
        """
        current_size = self.get_size()
        return max(0, self.max_size_bytes - current_size)

    def ensure_space(self, required_bytes: int) -> None:
        """Ensure sufficient space in cache, evicting models if needed.

        Args:
            required_bytes: Amount of space required in bytes.

        Raises:
            CacheError: If unable to free enough space.
        """
        available = self.get_available_space()

        if available >= required_bytes:
            logger.debug(f"Sufficient space available: {available / (1024**3):.2f} GB")
            return

        space_needed = required_bytes - available
        logger.info(f"Need to free {space_needed / (1024**3):.2f} GB of cache space")

        self.evict_lru(space_needed)

        # Check if we freed enough space
        final_available = self.get_available_space()
        if final_available < required_bytes:
            raise CacheError(
                f"Unable to free enough space. "
                f"Need {required_bytes / (1024**3):.2f} GB, "
                f"but only {final_available / (1024**3):.2f} GB available. "
                f"Consider increasing max_cache_size_gb or manually removing models."
            )

    def evict_lru(self, size_to_free: int) -> None:
        """Evict least recently used models to free space.

        Args:
            size_to_free: Amount of space to free in bytes.

        Raises:
            CacheError: If unable to free enough space.
        """
        freed = 0
        lru_models = self.registry.get_lru_models(exclude_pinned=True)

        if not lru_models:
            raise CacheError("No models available for eviction (all pinned). Unpin some models or increase cache size.")

        logger.info(f"Evicting LRU models to free {size_to_free / (1024**3):.2f} GB")

        for model in lru_models:
            if freed >= size_to_free:
                break

            logger.info(f"Evicting model: {model.model_id} ({model.size_gb:.2f} GB)")

            try:
                # Remove model files
                if model.path.exists():
                    shutil.rmtree(model.path)

                # Unregister from registry
                self.registry.unregister(model.model_id)

                freed += model.size_bytes
                logger.info(f"Evicted {model.model_id}, freed {freed / (1024**3):.2f} GB total")

            except Exception as e:
                logger.error(f"Failed to evict {model.model_id}: {e}")
                # Continue trying to evict other models
                continue

        if freed < size_to_free:
            raise CacheError(f"Only freed {freed / (1024**3):.2f} GB, but needed {size_to_free / (1024**3):.2f} GB")

    def remove(self, model_id: str) -> None:
        """Remove a specific model from the cache.

        Args:
            model_id: The model ID to remove.

        Raises:
            CacheError: If removal fails.
        """
        logger.info(f"Removing model from cache: {model_id}")

        try:
            model = self.registry.get(model_id)

            # Remove model files
            if model.path.exists():
                shutil.rmtree(model.path)

            # Unregister
            self.registry.unregister(model_id)

            logger.info(f"Removed {model_id} from cache")

        except Exception as e:
            logger.error(f"Failed to remove {model_id}: {e}")
            raise CacheError(f"Failed to remove model: {e}") from e

    def clear(self) -> None:
        """Clear all non-pinned models from the cache.

        Raises:
            CacheError: If clearing fails.
        """
        logger.warning("Clearing all non-pinned models from cache")

        models = self.registry.list_models()
        cleared = 0
        errors = []

        for model in models:
            if model.is_pinned:
                logger.info(f"Skipping pinned model: {model.model_id}")
                continue

            try:
                self.remove(model.model_id)
                cleared += 1
            except Exception as e:
                errors.append(f"{model.model_id}: {e}")

        logger.info(f"Cleared {cleared} models from cache")

        if errors:
            error_msg = "; ".join(errors)
            raise CacheError(f"Some models failed to clear: {error_msg}")

    def get_cache_info(self) -> dict[str, Any]:
        """Get information about the cache.

        Returns:
            Dictionary with cache statistics.
        """
        total_size = self.get_size()
        available_size = self.get_available_space()
        models = self.registry.list_models()

        return {
            "total_size_gb": total_size / (1024**3),
            "max_size_gb": self.max_size_gb,
            "available_gb": available_size / (1024**3),
            "usage_percent": (total_size / self.max_size_bytes * 100) if self.max_size_bytes else 0,
            "model_count": len(models),
            "pinned_count": sum(1 for m in models if m.is_pinned),
        }
