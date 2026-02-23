"""Audio processing utilities for voice reference preparation."""

import logging
from pathlib import Path

from ttsx.utils.exceptions import InvalidAudioFileError

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}

# Recommended cloning duration range in seconds
MIN_CLONING_DURATION = 3.0
MAX_CLONING_DURATION = 30.0
RECOMMENDED_DURATION = (5.0, 15.0)


def validate_audio(audio_path: Path) -> None:
    """Validate that an audio file exists and has a supported format.

    Args:
        audio_path: Path to the audio file

    Raises:
        InvalidAudioFileError: If the file doesn't exist or format is unsupported
    """
    if not audio_path.exists():
        raise InvalidAudioFileError(str(audio_path), "file not found")

    suffix = audio_path.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise InvalidAudioFileError(
            str(audio_path),
            f"unsupported format '{suffix}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}",
        )


def get_audio_info(audio_path: Path) -> dict:
    """Return basic metadata about an audio file.

    Args:
        audio_path: Path to the audio file

    Returns:
        Dict with keys: duration, sample_rate, channels, format
    """
    try:
        import soundfile as sf

        info = sf.info(str(audio_path))
        return {
            "duration": info.duration,
            "sample_rate": info.samplerate,
            "channels": info.channels,
            "format": info.format,
        }
    except Exception as e:
        logger.warning("Could not read audio info for %s: %s", audio_path, e)
        return {"duration": 0.0, "sample_rate": 0, "channels": 0, "format": "unknown"}


def check_cloning_suitability(audio_path: Path) -> list[str]:
    """Check whether an audio file is suitable for voice cloning.

    Performs non-fatal quality checks and returns a list of advisory
    warnings that the caller can display to the user.

    Args:
        audio_path: Path to the reference audio file

    Returns:
        List of warning strings (empty list means all checks passed)
    """
    warnings: list[str] = []

    info = get_audio_info(audio_path)
    duration = info.get("duration", 0.0)

    if duration < MIN_CLONING_DURATION:
        warnings.append(
            f"Reference audio is very short ({duration:.1f}s). "
            f"For best results, use at least {MIN_CLONING_DURATION:.0f}s of clean speech."
        )
    elif duration > MAX_CLONING_DURATION:
        warnings.append(
            f"Reference audio is long ({duration:.1f}s). "
            f"Models typically only use the first {MAX_CLONING_DURATION:.0f}s."
        )

    sr = info.get("sample_rate", 0)
    if 0 < sr < 16000:
        warnings.append(
            f"Low sample rate ({sr}Hz). For best quality, use audio recorded at 16kHz or higher."
        )

    return warnings


def prepare_audio_for_cloning(
    audio_path: Path,
    target_sample_rate: int | None = None,
    normalize: bool = True,
) -> tuple:
    """Load and pre-process reference audio for voice cloning.

    Steps:
    1. Validate the file exists and format is supported
    2. Load with soundfile
    3. Convert stereo → mono
    4. Resample to target_sample_rate (if provided and librosa available)
    5. Normalize amplitude to 95% of maximum

    Args:
        audio_path: Path to reference audio
        target_sample_rate: Resample to this rate; skipped if None
        normalize: Whether to peak-normalize the amplitude

    Returns:
        Tuple of ``(audio_array, sample_rate)`` as numpy arrays

    Raises:
        InvalidAudioFileError: If the file cannot be loaded
    """
    try:
        import numpy as np
        import soundfile as sf
    except ImportError as e:
        raise RuntimeError(
            "soundfile is required for audio processing. Install with:\n  uv add soundfile"
        ) from e

    validate_audio(audio_path)

    try:
        audio, sr = sf.read(str(audio_path))
    except Exception as e:
        raise InvalidAudioFileError(str(audio_path), f"could not read file: {e}") from e

    # Stereo → mono
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
        logger.debug("Converted stereo to mono")

    # Resample if requested and librosa is available
    if target_sample_rate is not None and sr != target_sample_rate:
        try:
            import librosa

            audio = librosa.resample(
                audio.astype(np.float32), orig_sr=sr, target_sr=target_sample_rate
            )
            logger.debug("Resampled from %dHz to %dHz", sr, target_sample_rate)
            sr = target_sample_rate
        except ImportError:
            logger.debug("librosa not available, skipping resample")

    # Peak-normalize
    if normalize:
        peak = np.abs(audio).max()
        if peak > 0:
            audio = audio / peak * 0.95

    return audio, sr
