"""Text-to-speech generation engine with model-specific implementations."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from huggingface_hub import ModelInfo

from ttsx.config import get_config
from ttsx.models.registry import ModelRegistry

logger = logging.getLogger(__name__)


class TTSEngine(ABC):
    """Abstract base class for TTS generation engines.
    
    Each model type should extend this and implement the generate method.
    """

    def __init__(self):
        """Initialize TTS engine."""
        self.config = get_config()
        self.registry = ModelRegistry()
        self.loaded_model = None
        self.loaded_model_id = None

    @abstractmethod
    def generate(
        self,
        text: str,
        model_id: str,
        model_path: Path,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> Path:
        """Generate speech from text.

        Args:
            text: Text to convert to speech
            model_id: Model ID being used
            model_path: Path to model directory
            output_path: Output WAV file path (auto-generated if None)
            **kwargs: Additional model-specific parameters

        Returns:
            Path to generated audio file

        Raises:
            RuntimeError: If generation fails
        """
        pass

    def _generate_output_path(self, text: str) -> Path:
        """Generate auto output path based on text and timestamp.

        Args:
            text: Input text

        Returns:
            Path for output file
        """
        from datetime import datetime

        # Create safe filename from first few words
        words = text.split()[:5]
        safe_name = "_".join(w.lower() for w in words if w.isalnum())
        if not safe_name:
            safe_name = "output"

        # Add timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_{timestamp}.wav"

        # Use current directory or configured output directory
        output_dir = Path.cwd()
        return output_dir / filename


class QwenTTSEngine(TTSEngine):
    """TTS engine for Qwen3-TTS models (PyTorch/Transformers)."""

    def generate(
        self,
        text: str,
        model_id: str,
        model_path: Path,
        output_path: Optional[Path] = None,
        voice: Optional[str] = None,
        ref_audio: Optional[Path] = None,
        ref_text: Optional[str] = None,
        instruct: Optional[str] = None,
        **kwargs,
    ) -> Path:
        """Generate speech using Qwen3-TTS models.

        Args:
            text: Text to convert to speech
            model_id: Model ID being used
            model_path: Path to model directory
            output_path: Output WAV file path
            voice: Predefined voice name (for CustomVoice models)
            ref_audio: Reference audio file (for Base models)
            ref_text: Reference audio transcript (for Base models)
            instruct: Style instruction (for CustomVoice/VoiceDesign)
            **kwargs: Additional parameters

        Returns:
            Path to generated audio file

        Raises:
            RuntimeError: If generation fails
        """
        try:
            from qwen_tts import Qwen3TTSModel
            import torch
            import scipy.io.wavfile as wavfile
            import numpy as np
        except ImportError as e:
            raise RuntimeError(
                "qwen-tts not installed. Install with:\n"
                "  uv add qwen-tts"
            ) from e

        # Generate output path if not provided
        if output_path is None:
            output_path = self._generate_output_path(text)

        logger.info(f"Loading Qwen3-TTS model from {model_path}")

        # Determine model type from name
        is_base = "base" in model_id.lower() and "custom" not in model_id.lower()
        is_custom_voice = "customvoice" in model_id.lower()
        is_voice_design = "voicedesign" in model_id.lower()

        # Load model (cache it if same as last time)
        if self.loaded_model_id != str(model_path):
            logger.info("Loading model with qwen_tts library...")
            self.loaded_model = Qwen3TTSModel.from_pretrained(
                str(model_path),
                torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
                device_map="cuda" if torch.cuda.is_available() else "cpu",
            )
            self.loaded_model_id = str(model_path)
            logger.info(f"Model loaded successfully: {type(self.loaded_model).__name__}")

        logger.info(f"Generating speech: '{text[:50]}{'...' if len(text) > 50 else ''}'")

        # Generate based on model type
        try:
            if is_custom_voice:
                # CustomVoice model - use predefined speakers
                speaker = voice.lower() if voice else "ryan"
                logger.info(f"Using CustomVoice model with speaker: {speaker}")

                wavs, sr = self.loaded_model.generate_custom_voice(
                    text=text,
                    language="Auto",
                    speaker=speaker,
                    instruct=instruct,
                    non_streaming_mode=True,
                    max_new_tokens=2048,
                )

            elif is_voice_design:
                # VoiceDesign model - use voice description
                voice_instruct = instruct or "Speak in a clear and natural tone."
                logger.info(f"Using VoiceDesign model with instruction: {voice_instruct}")

                wavs, sr = self.loaded_model.generate_voice_design(
                    text=text,
                    language="Auto",
                    instruct=voice_instruct,
                    non_streaming_mode=True,
                    max_new_tokens=2048,
                )

            elif is_base:
                # Base model - requires reference audio for voice cloning
                if not ref_audio:
                    raise ValueError(
                        "Base models require reference audio for voice cloning.\n"
                        "Use --ref-audio <file> --ref-text <transcript>\n"
                        "Or install a CustomVoice model instead:\n"
                        "  ttsx install Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
                    )

                logger.info(f"Using Base model for voice cloning from: {ref_audio}")

                # Load reference audio
                import soundfile as sf
                ref_wav, ref_sr = sf.read(str(ref_audio))

                wavs, sr = self.loaded_model.generate_voice_clone(
                    text=text,
                    language="Auto",
                    ref_audio=(ref_wav, ref_sr),
                    ref_text=ref_text,
                    x_vector_only_mode=not ref_text,  # Use x-vector if no transcript
                    max_new_tokens=2048,
                )

            else:
                # Unknown type - try CustomVoice method as fallback
                logger.warning("Unknown model type, trying CustomVoice API")
                speaker = voice.lower() if voice else "ryan"
                wavs, sr = self.loaded_model.generate_custom_voice(
                    text=text,
                    language="Auto",
                    speaker=speaker,
                    non_streaming_mode=True,
                    max_new_tokens=2048,
                )

            # Save audio
            audio = wavs[0]  # Get first waveform

            # Normalize to int16 range if needed
            if audio.dtype != np.int16:
                audio_normalized = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
            else:
                audio_normalized = audio

            # Write WAV file
            wavfile.write(str(output_path), sr, audio_normalized)

            logger.info(f"Audio generated successfully: {output_path}")
            return output_path

        except AttributeError as e:
            logger.error(f"Model API error: {e}")
            raise RuntimeError(
                f"Model '{model_id}' doesn't support the expected API. "
                f"Error: {e}"
            ) from e
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise RuntimeError(f"Failed to generate audio: {e}") from e

    def list_available_voices(self) -> list[str]:
        """List available predefined voices for Qwen models.

        Returns:
            List of voice names
        """
        return [
            "Aiden",
            "Dylan",
            "Eric",
            "Ono_anna",
            "Ryan",
            "Serena",
            "Sohee",
            "Uncle_fu",
            "Vivian",
        ]


class MLXTTSEngine(TTSEngine):
    """TTS engine for MLX-optimized models (Apple Silicon only)."""

    def generate(
        self,
        text: str,
        model_id: str,
        model_path: Path,
        output_path: Optional[Path] = None,
        voice: Optional[str] = None,
        ref_audio: Optional[Path] = None,
        ref_text: Optional[str] = None,
        **kwargs,
    ) -> Path:
        """Generate speech using MLX models.

        Args:
            text: Text to convert
            model_id: Model ID being used
            model_path: Path to model directory
            output_path: Output file path
            voice: Predefined voice name
            ref_audio: Reference audio for cloning
            ref_text: Reference audio transcript
            **kwargs: Additional parameters

        Returns:
            Path to generated audio file

        Raises:
            RuntimeError: If MLX not available or generation fails
        """
        try:
            import mlx.core as mx
            from mlx_audio.tts.generate import generate_audio
            from mlx_audio.tts.utils import load_model
        except ImportError as e:
            raise RuntimeError(
                "MLX models require Apple Silicon (ARM64 Mac). "
                "Your system doesn't support MLX.\n\n"
                "Please install a PyTorch-based TTS model instead:\n"
                "  ttsx search qwen tts --compatible\n"
                "  ttsx install Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
            ) from e

        # Generate output path if not provided
        if output_path is None:
            output_path = self._generate_output_path(text)

        logger.info(f"Loading MLX model from {model_path}")

        # Load model (cache it if same as last time)
        if self.loaded_model_id != str(model_path):
            self.loaded_model = load_model(str(model_path))
            self.loaded_model_id = str(model_path)
            logger.info("MLX model loaded successfully")

        # Prepare generation kwargs
        gen_kwargs = {
            "model": self.loaded_model,
            "text": text,
            "file_prefix": str(output_path.parent / output_path.stem),
        }

        if voice:
            gen_kwargs["voice"] = voice
            logger.info(f"Using predefined voice: {voice}")

        if ref_audio and ref_text:
            gen_kwargs["ref_audio"] = str(ref_audio)
            gen_kwargs["ref_text"] = ref_text
            logger.info(f"Using voice cloning with reference: {ref_audio}")

        # Generate audio
        logger.info(f"Generating speech: '{text[:50]}{'...' if len(text) > 50 else ''}'")
        result = generate_audio(**gen_kwargs)

        # mlx-audio appends .wav extension
        actual_output = Path(f"{gen_kwargs['file_prefix']}.wav")

        if actual_output.exists():
            logger.info(f"Audio generated successfully: {actual_output}")
            return actual_output
        else:
            raise RuntimeError(f"Generation failed - output file not created: {actual_output}")

    def list_available_voices(self) -> list[str]:
        """List available predefined voices for MLX models.

        Returns:
            List of voice names
        """
        # MLX Qwen models use same voices
        return [
            "Chelsie",
            "Ethan",
            "Serena",
            "Vivian",
            "Ryan",
            "Aiden",
            "Eric",
            "Dylan",
        ]


def get_tts_engine(model_id: str) -> TTSEngine:
    """Factory function to get appropriate TTS engine for a model.

    Args:
        model_id: Model ID to determine engine type

    Returns:
        Appropriate TTSEngine subclass instance

    Raises:
        NotImplementedError: If model type not supported
    """
    model_id_lower = model_id.lower()

    # Check for MLX models
    if "mlx-community" in model_id_lower or "mlx" in model_id_lower:
        logger.info(f"Detected MLX model: {model_id}")
        return MLXTTSEngine()

    # Check for Qwen3-TTS models
    if "qwen3-tts" in model_id_lower or "qwen3_tts" in model_id_lower or "qwen/qwen3-tts" in model_id_lower:
        logger.info(f"Detected Qwen3-TTS model: {model_id}")
        return QwenTTSEngine()

    # Unknown model type
    raise NotImplementedError(
        f"Model '{model_id}' is not yet supported.\n"
        f"Supported model types:\n"
        f"  - Qwen3-TTS models (Qwen/Qwen3-TTS-*)\n"
        f"  - MLX models (mlx-community/*)\n"
    )
