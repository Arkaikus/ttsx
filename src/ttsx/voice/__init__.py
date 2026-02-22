"""Voice cloning and profile management."""

from ttsx.voice.cloner import clone_with_audio, clone_with_profile
from ttsx.voice.encoder import (
    SUPPORTED_FORMATS,
    check_cloning_suitability,
    get_audio_info,
    prepare_audio_for_cloning,
    validate_audio,
)
from ttsx.voice.profiles import VoiceProfile, VoiceProfileManager

__all__ = [
    "VoiceProfile",
    "VoiceProfileManager",
    "clone_with_profile",
    "clone_with_audio",
    "validate_audio",
    "prepare_audio_for_cloning",
    "get_audio_info",
    "check_cloning_suitability",
    "SUPPORTED_FORMATS",
]
