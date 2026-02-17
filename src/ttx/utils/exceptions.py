"""Custom exceptions for ttx."""


class TTXError(Exception):
    """Base exception for all ttx errors."""

    pass


class ModelNotFoundError(TTXError):
    """Raised when a requested model is not found."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        super().__init__(
            f"Model '{model_name}' not found. "
            f"Search for models with: ttx search {model_name}"
        )


class ModelNotInstalledError(TTXError):
    """Raised when trying to use a model that isn't installed."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        super().__init__(
            f"Model '{model_name}' is not installed. "
            f"Install it with: ttx install {model_name}"
        )


class ModelDownloadError(TTXError):
    """Raised when model download fails."""

    def __init__(self, model_name: str, reason: str) -> None:
        self.model_name = model_name
        self.reason = reason
        super().__init__(f"Failed to download '{model_name}': {reason}")


class AudioGenerationError(TTXError):
    """Raised when audio generation fails."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Audio generation failed: {reason}")


class VoiceCloningError(TTXError):
    """Raised when voice cloning fails."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Voice cloning failed: {reason}")


class InvalidAudioFileError(TTXError):
    """Raised when an audio file is invalid or cannot be loaded."""

    def __init__(self, filepath: str, reason: str) -> None:
        self.filepath = filepath
        self.reason = reason
        super().__init__(f"Invalid audio file '{filepath}': {reason}")


class ConfigurationError(TTXError):
    """Raised when there's a configuration problem."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Configuration error: {message}")


class CacheError(TTXError):
    """Raised when there's a cache-related problem."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Cache error: {message}")


class InsufficientVRAMError(TTXError):
    """Raised when there's not enough VRAM to load a model."""

    def __init__(self, required_gb: float, available_gb: float) -> None:
        self.required_gb = required_gb
        self.available_gb = available_gb
        super().__init__(
            f"Insufficient VRAM: model requires ~{required_gb:.1f}GB, "
            f"but only {available_gb:.1f}GB available. "
            f"Consider using a smaller model or CPU mode."
        )
