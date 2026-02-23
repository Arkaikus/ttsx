"""Voice cloning logic bridging voice profiles and TTS engines."""

import logging
from pathlib import Path
from typing import Optional

from ttsx.generation.engine import get_tts_engine
from ttsx.models.registry import ModelRegistry
from ttsx.utils.exceptions import ModelNotInstalledError, VoiceCloningError
from ttsx.voice.encoder import check_cloning_suitability, validate_audio
from ttsx.voice.profiles import VoiceProfile, VoiceProfileManager

logger = logging.getLogger(__name__)


def _resolve_model(model_id: Optional[str], registry: ModelRegistry) -> str:
    """Resolve which installed model to use.

    Args:
        model_id: Explicit model ID, or None to auto-select
        registry: Model registry instance

    Returns:
        Resolved model ID string

    Raises:
        ModelNotInstalledError: If no models are installed or specified model not found
    """
    if model_id is not None:
        if not registry.is_installed(model_id):
            raise ModelNotInstalledError(model_id)
        return model_id

    installed = list(registry.list_models())
    if not installed:
        raise ModelNotInstalledError(
            "No models installed. Install one first:\n"
            "  ttsx install Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
        )
    return installed[0].model_id


def clone_with_profile(
    text: str,
    profile_name: str,
    model_id: Optional[str] = None,
    output_path: Optional[Path] = None,
) -> Path:
    """Generate speech by cloning a voice from a saved profile.

    Args:
        text: Text to synthesize
        profile_name: Name of the saved :class:`~ttsx.voice.profiles.VoiceProfile`
        model_id: TTS model to use (auto-selects first installed if None)
        output_path: Output WAV path (auto-generated if None)

    Returns:
        Path to the generated audio file

    Raises:
        VoiceCloningError: If the profile doesn't exist or reference audio is missing
        ModelNotInstalledError: If no suitable model is installed
    """
    manager = VoiceProfileManager()
    profile = manager.get(profile_name)

    if profile is None:
        available = [p.name for p in manager.list_profiles()]
        hint = (
            f"Available profiles: {', '.join(available)}"
            if available
            else "No profiles saved yet. Add one with: ttsx voices add <name> <audio.wav>"
        )
        raise VoiceCloningError(f"Voice profile '{profile_name}' not found. {hint}")

    if not profile.audio_exists:
        raise VoiceCloningError(
            f"Reference audio for profile '{profile_name}' is missing: {profile.audio_path}\n"
            f"Re-add the profile with a new audio file:\n"
            f"  ttsx voices add {profile_name} <path/to/audio.wav> --overwrite"
        )

    return _run_cloning(
        text=text,
        audio_path=profile.audio_path,
        ref_text=profile.ref_text,
        model_id=model_id,
        output_path=output_path,
    )


def clone_with_audio(
    text: str,
    audio_path: Path,
    model_id: Optional[str] = None,
    ref_text: Optional[str] = None,
    output_path: Optional[Path] = None,
) -> tuple[Path, list[str]]:
    """Generate speech by cloning a voice from an audio file directly.

    Unlike :func:`clone_with_profile`, this does not require saving a profile
    first. The reference audio is validated before generation starts.

    Args:
        text: Text to synthesize
        audio_path: Reference audio file (WAV, MP3, FLAC, …)
        model_id: TTS model to use (auto-selects first installed if None)
        ref_text: Transcript of the reference audio (strongly recommended)
        output_path: Output WAV path (auto-generated if None)

    Returns:
        Tuple of ``(output_path, warnings)`` where ``warnings`` is a list
        of advisory strings about audio quality

    Raises:
        InvalidAudioFileError: If the audio file cannot be loaded
        ModelNotInstalledError: If no suitable model is installed
    """
    validate_audio(audio_path)
    warnings = check_cloning_suitability(audio_path)

    generated = _run_cloning(
        text=text,
        audio_path=audio_path,
        ref_text=ref_text,
        model_id=model_id,
        output_path=output_path,
    )
    return generated, warnings


def _run_cloning(
    text: str,
    audio_path: Path,
    ref_text: Optional[str],
    model_id: Optional[str],
    output_path: Optional[Path],
) -> Path:
    """Internal: wire up engine and call generate.

    Args:
        text: Text to synthesize
        audio_path: Validated reference audio path
        ref_text: Optional transcript of the reference
        model_id: Resolved or explicit model ID
        output_path: Output path

    Returns:
        Path to generated audio file
    """
    registry = ModelRegistry()
    resolved_id = _resolve_model(model_id, registry)
    model_info = registry.get(resolved_id)

    if model_info is None:
        raise ModelNotInstalledError(resolved_id)

    logger.info("Cloning voice from %s using model %s", audio_path.name, resolved_id)

    engine = get_tts_engine(resolved_id)
    return engine.generate(
        text=text,
        model_id=resolved_id,
        model_path=model_info.path,
        output_path=output_path,
        ref_audio=audio_path,
        ref_text=ref_text,
    )
