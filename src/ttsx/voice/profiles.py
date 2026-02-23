"""Voice profile management for persistent voice cloning."""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from ttsx.config import get_config
from ttsx.utils.exceptions import VoiceCloningError


class VoiceProfile(BaseModel):
    """A saved voice profile with reference audio for voice cloning."""

    name: str = Field(..., description="Unique profile name")
    audio_path: Path = Field(..., description="Path to stored reference audio file")
    ref_text: str | None = Field(None, description="Transcript of reference audio")
    description: str | None = Field(None, description="Optional description")
    language: str | None = Field(None, description="Language of the voice")
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = {"frozen": False}

    @property
    def audio_exists(self) -> bool:
        """Check if the reference audio file exists."""
        return self.audio_path.exists()

    def format_created(self) -> str:
        """Return a human-friendly creation date string."""
        return self.created_at.strftime("%Y-%m-%d %H:%M")


class VoiceProfileManager:
    """Manages saved voice profiles for voice cloning.

    Profiles are stored as JSON at ``~/.ttsx/voices/profiles.json``.
    Reference audio files are copied to ``~/.ttsx/voices/audio/`` so they
    remain available even if the original is moved or deleted.
    """

    def __init__(self) -> None:
        config = get_config()
        self.voices_dir = config.config_dir / "voices"
        self.audio_dir = self.voices_dir / "audio"
        self.profiles_file = self.voices_dir / "profiles.json"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create voice profile directories if they don't exist."""
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def _load_profiles(self) -> dict[str, VoiceProfile]:
        """Load profiles from JSON file."""
        if not self.profiles_file.exists():
            return {}

        try:
            data = json.loads(self.profiles_file.read_text(encoding="utf-8"))
            return {
                name: VoiceProfile(**{**entry, "audio_path": Path(entry["audio_path"])})
                for name, entry in data.items()
            }
        except (json.JSONDecodeError, KeyError, ValueError):
            return {}

    def _save_profiles(self, profiles: dict[str, VoiceProfile]) -> None:
        """Persist profiles to JSON file."""
        serialized: dict[str, dict] = {}
        for name, profile in profiles.items():
            d = profile.model_dump()
            d["audio_path"] = str(profile.audio_path)
            d["created_at"] = profile.created_at.isoformat()
            serialized[name] = d
        self.profiles_file.write_text(json.dumps(serialized, indent=2), encoding="utf-8")

    def add(
        self,
        name: str,
        audio_file: Path,
        ref_text: str | None = None,
        description: str | None = None,
        language: str | None = None,
        overwrite: bool = False,
    ) -> "VoiceProfile":
        """Add a new voice profile.

        Copies the source audio file into the managed voices directory so the
        profile is self-contained even if the original file is removed.

        Args:
            name: Unique profile name (alphanumeric + underscores/hyphens)
            audio_file: Source audio file (WAV, MP3, FLAC, …)
            ref_text: Transcript of the reference audio (strongly recommended)
            description: Optional human-readable description
            language: Language spoken in the reference audio
            overwrite: Replace an existing profile with the same name

        Returns:
            Created :class:`VoiceProfile`

        Raises:
            VoiceCloningError: If name already exists (and overwrite=False) or
                audio file is not found
        """
        if not audio_file.exists():
            raise VoiceCloningError(f"Audio file not found: {audio_file}")

        profiles = self._load_profiles()

        if name in profiles and not overwrite:
            raise VoiceCloningError(
                f"Voice profile '{name}' already exists. "
                f"Use --overwrite to replace it, or remove it first:\n"
                f"  ttsx voices remove {name}"
            )

        # Copy audio into managed directory with profile name
        suffix = audio_file.suffix.lower() or ".wav"
        stored_audio = self.audio_dir / f"{name}{suffix}"
        shutil.copy2(audio_file, stored_audio)

        profile = VoiceProfile(
            name=name,
            audio_path=stored_audio,
            ref_text=ref_text,
            description=description,
            language=language,
        )
        profiles[name] = profile
        self._save_profiles(profiles)
        return profile

    def remove(self, name: str) -> bool:
        """Remove a voice profile and its stored audio.

        Args:
            name: Profile name to remove

        Returns:
            True if the profile was removed, False if it did not exist
        """
        profiles = self._load_profiles()

        if name not in profiles:
            return False

        profile = profiles[name]

        # Remove the stored audio file
        if profile.audio_path.exists():
            profile.audio_path.unlink()

        del profiles[name]
        self._save_profiles(profiles)
        return True

    def get(self, name: str) -> Optional["VoiceProfile"]:
        """Retrieve a voice profile by name.

        Args:
            name: Profile name

        Returns:
            :class:`VoiceProfile` or None if not found
        """
        return self._load_profiles().get(name)

    def list_profiles(self) -> list["VoiceProfile"]:
        """Return all saved voice profiles sorted by name."""
        return sorted(self._load_profiles().values(), key=lambda p: p.name)

    def exists(self, name: str) -> bool:
        """Check whether a profile with the given name exists."""
        return name in self._load_profiles()
