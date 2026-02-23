"""Model registry for tracking installed models."""

import json
import logging
from datetime import datetime
from pathlib import Path

from ttsx.config import get_config
from ttsx.models.types import InstalledModel
from ttsx.utils.exceptions import CacheError, ModelNotInstalledError

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Registry for tracking installed TTS models."""

    def __init__(self, registry_path: Path | None = None) -> None:
        """Initialize the model registry.

        Args:
            registry_path: Path to the registry file. Uses config default if None.
        """
        config = get_config()
        self.registry_path = registry_path or config.registry_path
        self.models: dict[str, InstalledModel] = {}
        self._load()

    def _load(self) -> None:
        """Load the registry from disk."""
        if not self.registry_path.exists():
            logger.debug("Registry file not found, starting with empty registry")
            return

        try:
            with open(self.registry_path) as f:
                data = json.load(f)

            self.models = {}
            for model_id, model_data in data.items():
                self.models[model_id] = InstalledModel(
                    model_id=model_data["model_id"],
                    path=Path(model_data["path"]),
                    installed_at=datetime.fromisoformat(model_data["installed_at"]),
                    size_bytes=model_data["size_bytes"],
                    last_used=(datetime.fromisoformat(model_data["last_used"]) if model_data.get("last_used") else None),
                    is_pinned=model_data.get("is_pinned", False),
                )

            logger.info(f"Loaded {len(self.models)} models from registry")

        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
            raise CacheError(f"Failed to load registry: {e}") from e

    def _save(self) -> None:
        """Save the registry to disk."""
        try:
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)

            data = {}
            for model_id, model in self.models.items():
                data[model_id] = {
                    "model_id": model.model_id,
                    "path": str(model.path),
                    "installed_at": model.installed_at.isoformat(),
                    "size_bytes": model.size_bytes,
                    "last_used": model.last_used.isoformat() if model.last_used else None,
                    "is_pinned": model.is_pinned,
                }

            with open(self.registry_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved registry with {len(self.models)} models")

        except Exception as e:
            logger.error(f"Failed to save registry: {e}")
            raise CacheError(f"Failed to save registry: {e}") from e

    def register(
        self,
        model_id: str,
        path: Path,
        size_bytes: int,
    ) -> InstalledModel:
        """Register a newly installed model.

        Args:
            model_id: The model ID.
            path: Path to the installed model.
            size_bytes: Size of the model in bytes.

        Returns:
            The registered InstalledModel.
        """
        logger.info(f"Registering model: {model_id}")

        model = InstalledModel(
            model_id=model_id,
            path=path,
            installed_at=datetime.now(),
            size_bytes=size_bytes,
        )

        self.models[model_id] = model
        self._save()

        return model

    def unregister(self, model_id: str) -> None:
        """Unregister a model.

        Args:
            model_id: The model ID to unregister.

        Raises:
            ModelNotInstalledError: If model is not registered.
        """
        if model_id not in self.models:
            raise ModelNotInstalledError(model_id)

        logger.info(f"Unregistering model: {model_id}")
        del self.models[model_id]
        self._save()

    def get(self, model_id: str) -> InstalledModel:
        """Get information about an installed model.

        Args:
            model_id: The model ID.

        Returns:
            The InstalledModel.

        Raises:
            ModelNotInstalledError: If model is not installed.
        """
        if model_id not in self.models:
            raise ModelNotInstalledError(model_id)

        return self.models[model_id]

    def list_models(self) -> list[InstalledModel]:
        """List all installed models.

        Returns:
            List of InstalledModel objects.
        """
        return list(self.models.values())

    def is_installed(self, model_id: str) -> bool:
        """Check if a model is installed.

        Args:
            model_id: The model ID.

        Returns:
            True if installed, False otherwise.
        """
        return model_id in self.models

    def update_last_used(self, model_id: str) -> None:
        """Update the last used timestamp for a model.

        Args:
            model_id: The model ID.

        Raises:
            ModelNotInstalledError: If model is not installed.
        """
        if model_id not in self.models:
            raise ModelNotInstalledError(model_id)

        self.models[model_id].last_used = datetime.now()
        self._save()
        logger.debug(f"Updated last used time for: {model_id}")

    def pin(self, model_id: str) -> None:
        """Pin a model to prevent it from being evicted.

        Args:
            model_id: The model ID.

        Raises:
            ModelNotInstalledError: If model is not installed.
        """
        if model_id not in self.models:
            raise ModelNotInstalledError(model_id)

        self.models[model_id].is_pinned = True
        self._save()
        logger.info(f"Pinned model: {model_id}")

    def unpin(self, model_id: str) -> None:
        """Unpin a model.

        Args:
            model_id: The model ID.

        Raises:
            ModelNotInstalledError: If model is not installed.
        """
        if model_id not in self.models:
            raise ModelNotInstalledError(model_id)

        self.models[model_id].is_pinned = False
        self._save()
        logger.info(f"Unpinned model: {model_id}")

    def get_total_size(self) -> int:
        """Get the total size of all installed models.

        Returns:
            Total size in bytes.
        """
        return sum(model.size_bytes for model in self.models.values())

    def get_lru_models(self, exclude_pinned: bool = True) -> list[InstalledModel]:
        """Get models sorted by least recently used.

        Args:
            exclude_pinned: If True, exclude pinned models.

        Returns:
            List of models sorted by LRU (oldest first).
        """
        models = list(self.models.values())

        if exclude_pinned:
            models = [m for m in models if not m.is_pinned]

        # Sort by last_used (None values last), then by installed_at
        models.sort(key=lambda m: m.last_used or m.installed_at)

        return models
