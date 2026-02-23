"""HuggingFace Hub integration for TTS models."""

import asyncio
import logging
from pathlib import Path
from typing import Callable, Optional

import httpx
from huggingface_hub import HfApi, hf_hub_url
from huggingface_hub.hf_api import ModelInfo
from huggingface_hub.utils import RepositoryNotFoundError

from ttsx.config import get_config
from ttsx.utils.exceptions import ModelDownloadError, ModelNotFoundError

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, int, int], None]  # filename, bytes_done, total_bytes


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
    ) -> list[ModelInfo]:
        """Search for TTS models on HuggingFace Hub.

        Args:
            query: Optional search query.
            limit: Maximum number of results.

        Returns:
            List of ModelInfo objects from HuggingFace Hub.
        """
        logger.debug(f"Searching for TTS models: query={query}, limit={limit}")

        try:
            search_query = query or "text-to-speech pytorch"
            return self.api.list_models(
                search=search_query,
                limit=limit,
                full=True,
            )
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
            return self.api.model_info(model_id)
        except RepositoryNotFoundError as e:
            logger.error(f"Model not found: {model_id}")
            raise ModelNotFoundError(model_id) from e
        except Exception as e:
            logger.error(f"Failed to get model info for {model_id}: {e}")
            raise ModelNotFoundError(model_id) from e

    async def download_model(
        self,
        model_id: str,
        cache_dir: Optional[Path] = None,
        on_progress: Optional[ProgressCallback] = None,
        max_concurrent: int = 4,
        model_info: Optional[ModelInfo] = None,
    ) -> Path:
        """Download a model file-by-file with async streaming and per-file progress.

        Files are downloaded concurrently (up to ``max_concurrent`` at a time),
        with small files prioritized first so config/tokenizer files finish quickly.
        Each 64 KB chunk triggers ``on_progress(filename, bytes_done, total_bytes)``.

        Args:
            model_id: The model ID to download.
            cache_dir: Target directory. Defaults to config value.
            on_progress: Called with (filename, bytes_done, total_bytes) per chunk.
            max_concurrent: Maximum simultaneous file downloads.
            model_info: Optional pre-fetched model info for ordering by size. If None, fetches internally.

        Returns:
            Path to the downloaded model directory.

        Raises:
            ModelDownloadError: If any file download fails.
        """
        config = get_config()
        cache_dir = cache_dir or config.models_cache_path
        target_dir = cache_dir / model_id.replace("/", "_")
        target_dir.mkdir(parents=True, exist_ok=True)

        if model_info is None:
            model_info = await asyncio.to_thread(self.api.model_info, model_id)
        siblings = model_info.siblings or []
        
        if not siblings:
            raise ModelDownloadError(model_id, f"No siblings found in model info {model_id}")
        
        files = [s.rfilename for s in sorted(siblings, key=lambda s: s.size or float("inf"))]

        auth_headers: dict[str, str] = {}
        if self.token:
            auth_headers["Authorization"] = f"Bearer {self.token}"

        async def _download_one(client: httpx.AsyncClient, filename: str) -> None:
            url = hf_hub_url(model_id, filename, repo_type="model")
            dest = target_dir / filename
            dest.parent.mkdir(parents=True, exist_ok=True)

            async with client.stream("GET", url, follow_redirects=True) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                done = 0
                with open(dest, "wb") as fh:
                    async for chunk in resp.aiter_bytes(chunk_size=65_536):
                        fh.write(chunk)
                        done += len(chunk)
                        if on_progress:
                            on_progress(filename, done, total)

        timeout = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=10.0)
        try:
            async with httpx.AsyncClient(headers=auth_headers, timeout=timeout) as client:
                await asyncio.gather(*[_download_one(client, f) for f in files])
        except httpx.HTTPError as e:
            raise ModelDownloadError(model_id, str(e)) from e
        except Exception as e:
            raise ModelDownloadError(model_id, str(e)) from e

        logger.info(f"Model downloaded to: {target_dir}")
        return target_dir
