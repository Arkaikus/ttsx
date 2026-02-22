"""Configuration management for ttsx."""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TTSXConfig(BaseSettings):
    """Main configuration for ttsx.

    Configuration is loaded from:
    1. Default values
    2. ~/.ttsx/config.toml (if exists)
    3. Environment variables (ttsx_*)
    """

    model_config = SettingsConfigDict(
        env_prefix="ttsx_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Paths
    cache_dir: Path = Field(
        default_factory=lambda: Path.home() / ".ttsx" / "models",
        description="Directory for cached models",
    )
    config_dir: Path = Field(
        default_factory=lambda: Path.home() / ".ttsx",
        description="Directory for configuration files",
    )

    # Cache settings
    max_cache_size_gb: int = Field(
        default=50,
        description="Maximum cache size in gigabytes",
        ge=1,
    )

    # Model settings
    default_model: Optional[str] = Field(
        default=None,
        description="Default TTS model to use",
    )
    device: Optional[str] = Field(
        default=None,
        description="Device to use (cuda, mps, cpu). Auto-detect if None.",
    )

    # HuggingFace settings
    hf_token: Optional[str] = Field(
        default=None,
        description="HuggingFace API token",
    )
    hf_cache_dir: Optional[Path] = Field(
        default=None,
        description="HuggingFace cache directory. Uses cache_dir if None.",
    )

    # Generation settings
    sample_rate: int = Field(
        default=22050,
        description="Default audio sample rate",
        ge=8000,
        le=48000,
    )
    output_format: str = Field(
        default="wav",
        description="Default output format",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose output",
    )

    def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        # Ensure directories exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)

    @property
    def models_cache_path(self) -> Path:
        """Get the models cache path."""
        return self.cache_dir

    @property
    def registry_path(self) -> Path:
        """Get the registry file path."""
        return self.config_dir / "registry.json"

    def get_device(self) -> str:
        """Get the device to use for model inference.

        Returns:
            Device string (cuda, mps, or cpu).
        """
        if self.device:
            return self.device

        # Auto-detect
        import torch

        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"


# Global configuration instance
_config: Optional[TTSXConfig] = None


def get_config() -> TTSXConfig:
    """Get the global configuration instance.

    Returns:
        The ttsxConfig instance.
    """
    global _config
    if _config is None:
        _config = TTSXConfig()
    return _config


def set_config(config: TTSXConfig) -> None:
    """Set the global configuration instance.

    Args:
        config: The new configuration.
    """
    global _config
    _config = config
