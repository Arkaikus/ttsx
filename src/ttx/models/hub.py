"""HuggingFace Hub integration for TTS models."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from huggingface_hub import HfApi, hf_hub_download, snapshot_download
from huggingface_hub.utils import RepositoryNotFoundError

from ttx.config import get_config
from ttx.models.types import ModelInfo
from ttx.utils.exceptions import ModelDownloadError, ModelNotFoundError

logger = logging.getLogger(__name__)


class HuggingFaceHub:
    """Interface to HuggingFace Hub for TTS models."""

    def __init__(self, token: Optional[str] = None) -> None:
        """Initialize HuggingFace Hub client.

        Args:
            token: Optional HuggingFace API token.
        """
        config = get_config()
        self.token = token or config.hf_token
        self.api = HfApi(token=self.token)

    def search_models(
        self,
        query: Optional[str] = None,
        limit: int = 20,
        sort: str = "modified",
    ) -> list[ModelInfo]:
        """Search for TTS models on HuggingFace Hub.

        Args:
            query: Optional search query.
            limit: Maximum number of results.
            sort: Sort order (modified, likes, downloads).

        Returns:
            List of ModelInfo objects.
        """
        logger.debug(f"Searching for TTS models: query={query}, limit={limit}, sort={sort}")

        try:
            # Search for TTS models
            # The newer API is simplified
            search_query = query or "text-to-speech pytorch"
            
            models = self.api.list_models(
                search=search_query,
                limit=limit,
            )

            results = []
            for model in models:
                try:
                    results.append(
                        ModelInfo(
                            model_id=model.id,
                            author=model.author or model.id.split("/")[0],
                            name=model.id.split("/")[-1],
                            downloads=model.downloads or 0,
                            likes=model.likes or 0,
                            last_modified=model.last_modified or datetime.now(),
                            tags=model.tags or [],
                            pipeline_tag=model.pipeline_tag or "text-to-speech",
                            library_name=getattr(model, "library_name", None),
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to parse model {model.id}: {e}")
                    continue

            logger.info(f"Found {len(results)} TTS models")
            return results

        except Exception as e:
            logger.error(f"Failed to search models: {e}")
            raise ModelNotFoundError(f"Search query: {query}") from e

    def get_model_info(self, model_id: str) -> ModelInfo:
        """Get detailed information about a specific model.

        Args:
            model_id: The model ID (e.g., "author/model-name").

        Returns:
            ModelInfo object.

        Raises:
            ModelNotFoundError: If model doesn't exist.
        """
        logger.debug(f"Getting info for model: {model_id}")

        try:
            model = self.api.model_info(model_id)

            return ModelInfo(
                model_id=model.id,
                author=model.author or model.id.split("/")[0],
                name=model.id.split("/")[-1],
                downloads=model.downloads or 0,
                likes=model.likes or 0,
                last_modified=model.last_modified or datetime.now(),
                tags=model.tags or [],
                pipeline_tag=model.pipeline_tag or "text-to-speech",
                library_name=getattr(model, "library_name", None),
            )

        except RepositoryNotFoundError as e:
            logger.error(f"Model not found: {model_id}")
            raise ModelNotFoundError(model_id) from e
        except Exception as e:
            logger.error(f"Failed to get model info for {model_id}: {e}")
            raise ModelNotFoundError(model_id) from e

    def download_model(
        self,
        model_id: str,
        cache_dir: Optional[Path] = None,
    ) -> Path:
        """Download a model from HuggingFace Hub.

        Args:
            model_id: The model ID to download.
            cache_dir: Directory to cache the model. Uses config default if None.

        Returns:
            Path to the downloaded model directory.

        Raises:
            ModelDownloadError: If download fails.
        """
        config = get_config()
        cache_dir = cache_dir or config.models_cache_path

        logger.info(f"Downloading model: {model_id}")

        try:
            # Download the full model repository
            model_path = snapshot_download(
                repo_id=model_id,
                cache_dir=str(cache_dir),
                token=self.token,
                local_dir=cache_dir / model_id.replace("/", "_"),
                local_dir_use_symlinks=False,
            )

            logger.info(f"Model downloaded successfully to: {model_path}")
            return Path(model_path)

        except RepositoryNotFoundError as e:
            logger.error(f"Model not found: {model_id}")
            raise ModelDownloadError(model_id, "Model not found on HuggingFace Hub") from e
        except Exception as e:
            logger.error(f"Failed to download model {model_id}: {e}")
            raise ModelDownloadError(model_id, str(e)) from e

    def download_file(
        self,
        model_id: str,
        filename: str,
        cache_dir: Optional[Path] = None,
    ) -> Path:
        """Download a specific file from a model repository.

        Args:
            model_id: The model ID.
            filename: Name of the file to download.
            cache_dir: Directory to cache the file.

        Returns:
            Path to the downloaded file.

        Raises:
            ModelDownloadError: If download fails.
        """
        config = get_config()
        cache_dir = cache_dir or config.models_cache_path

        logger.debug(f"Downloading file: {filename} from {model_id}")

        try:
            file_path = hf_hub_download(
                repo_id=model_id,
                filename=filename,
                cache_dir=str(cache_dir),
                token=self.token,
            )

            logger.debug(f"File downloaded: {file_path}")
            return Path(file_path)

        except Exception as e:
            logger.error(f"Failed to download file {filename} from {model_id}: {e}")
            raise ModelDownloadError(model_id, f"Failed to download {filename}: {e}") from e
