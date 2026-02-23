"""Hardware requirements and compatibility checking for models.

This module provides utilities to check if models are compatible with
the current hardware, estimate VRAM requirements, and detect quantized versions.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from huggingface_hub.hf_api import ModelInfo

from ttsx.hardware import HardwareDetector
from ttsx.models.types import get_model_size

logger = logging.getLogger(__name__)


class CompatibilityStatus(Enum):
    """Model compatibility with current hardware."""

    FITS = "fits"  # Model fits comfortably in VRAM
    TIGHT = "tight"  # Model fits but with <20% headroom
    TOO_LARGE = "too_large"  # Model won't fit in VRAM
    UNKNOWN = "unknown"  # Can't determine (no size or VRAM info)
    CPU_ONLY = "cpu_only"  # No GPU available, will run on CPU


class Precision(Enum):
    """Model precision/quantization level."""

    FP32 = "fp32"
    FP16 = "fp16"
    BF16 = "bf16"
    INT8 = "int8"
    INT4 = "int4"
    UNKNOWN = "unknown"


@dataclass
class VRAMEstimate:
    """VRAM usage estimate for a model."""

    model_size_gb: float
    precision: Precision
    overhead_multiplier: float
    estimated_vram_gb: float
    available_vram_gb: float
    headroom_gb: float
    headroom_percent: float

    @property
    def fits(self) -> bool:
        """Whether model fits in available VRAM."""
        return self.headroom_gb >= 0

    @property
    def is_tight(self) -> bool:
        """Whether fit is tight (<20% headroom)."""
        return 0 <= self.headroom_percent < 20


class HardwareRequirements:
    """Check hardware compatibility for TTS models."""

    # VRAM overhead multipliers by precision
    OVERHEAD_MULTIPLIERS = {
        Precision.FP32: 1.5,  # 50% overhead for activations, KV cache
        Precision.FP16: 1.2,  # 20% overhead
        Precision.BF16: 1.2,  # Same as FP16
        Precision.INT8: 1.15,  # 15% overhead
        Precision.INT4: 1.1,  # 10% overhead
        Precision.UNKNOWN: 1.3,  # Conservative default
    }

    # Quantization patterns in model IDs/tags
    QUANTIZATION_PATTERNS = {
        Precision.INT8: [
            r"int8",
            r"8bit",
            r"q8",
            r"quantized",
        ],
        Precision.INT4: [
            r"int4",
            r"4bit",
            r"q4",
            r"gguf",
            r"awq",
            r"gptq",
        ],
        Precision.FP16: [
            r"fp16",
            r"float16",
            r"half",
        ],
        Precision.BF16: [
            r"bf16",
            r"bfloat16",
        ],
    }

    def __init__(self):
        """Initialize with current hardware info."""
        self.hw_detector = HardwareDetector()
        self.hw_info = self.hw_detector.detect()
        self._available_vram_gb: Optional[float] = None

        # Cache available VRAM
        if self.hw_info.cuda_available and self.hw_info.gpus:
            # Get first GPU's available VRAM
            gpu = self.hw_info.gpus[0]
            if gpu.memory:
                self._available_vram_gb = gpu.memory.available_gb

    @property
    def available_vram_gb(self) -> Optional[float]:
        """Available VRAM in GB (first GPU), or None if CPU-only or unknown."""
        return self._available_vram_gb

    def detect_precision(self, model: ModelInfo) -> Precision:
        """Detect model precision from ID and tags.

        Args:
            model: HuggingFace ModelInfo

        Returns:
            Detected precision level
        """
        model_text = f"{model.id} {' '.join(model.tags or [])}".lower()

        # Check quantization patterns
        for precision, patterns in self.QUANTIZATION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, model_text):
                    logger.debug(f"Detected {precision.value} for {model.id}")
                    return precision

        # Default to FP32 if no indicators found
        return Precision.FP32

    def estimate_vram(
        self,
        model: ModelInfo,
        size_bytes: Optional[int] = None,
    ) -> Optional[VRAMEstimate]:
        """Estimate VRAM requirements for a model.

        Args:
            model: HuggingFace ModelInfo
            size_bytes: Model size in bytes (if known)

        Returns:
            VRAM estimate or None if can't estimate
        """
        # Get model size
        if size_bytes is None:
            size_bytes = get_model_size(model, fetch_accurate=False)

        if size_bytes is None:
            return None

        if self._available_vram_gb is None:
            return None

        # Convert to GB
        model_size_gb = size_bytes / (1024**3)

        # Detect precision
        precision = self.detect_precision(model)
        multiplier = self.OVERHEAD_MULTIPLIERS[precision]

        # Estimate total VRAM needed
        estimated_vram_gb = model_size_gb * multiplier

        # Calculate headroom
        headroom_gb = self._available_vram_gb - estimated_vram_gb
        headroom_percent = (
            (headroom_gb / self._available_vram_gb) * 100 if self._available_vram_gb > 0 else 0
        )

        return VRAMEstimate(
            model_size_gb=model_size_gb,
            precision=precision,
            overhead_multiplier=multiplier,
            estimated_vram_gb=estimated_vram_gb,
            available_vram_gb=self._available_vram_gb,
            headroom_gb=headroom_gb,
            headroom_percent=headroom_percent,
        )

    def check_compatibility(
        self,
        model: ModelInfo,
        size_bytes: Optional[int] = None,
    ) -> CompatibilityStatus:
        """Check if model is compatible with current hardware.

        Args:
            model: HuggingFace ModelInfo
            size_bytes: Model size in bytes (if known)

        Returns:
            Compatibility status
        """
        # CPU-only mode
        if not self.hw_info.cuda_available:
            return CompatibilityStatus.CPU_ONLY

        # No VRAM info available
        if self._available_vram_gb is None:
            return CompatibilityStatus.UNKNOWN

        # Estimate VRAM
        estimate = self.estimate_vram(model, size_bytes)
        if estimate is None:
            return CompatibilityStatus.UNKNOWN

        # Check fit
        if not estimate.fits:
            return CompatibilityStatus.TOO_LARGE
        elif estimate.is_tight:
            return CompatibilityStatus.TIGHT
        else:
            return CompatibilityStatus.FITS

    def find_quantized_versions(self, model: ModelInfo) -> list[str]:
        """Find potential quantized versions of a model.

        Args:
            model: Base model to find quantized versions for

        Returns:
            List of potential quantized model IDs
        """
        suggestions = []
        model_id = model.id
        author, name = model_id.split("/") if "/" in model_id else ("", model_id)

        # Common quantization suffixes
        quantization_patterns = [
            "-int8",
            "-int4",
            "-fp16",
            "-4bit",
            "-8bit",
            "-awq",
            "-gptq",
            "-gguf",
        ]

        for pattern in quantization_patterns:
            if pattern.lower() not in name.lower():
                suggestions.append(f"{author}/{name}{pattern}")

        return suggestions[:3]  # Return top 3 suggestions

    def format_compatibility(
        self,
        status: CompatibilityStatus,
        estimate: Optional[VRAMEstimate] = None,
    ) -> str:
        """Format compatibility status for display.

        Args:
            status: Compatibility status
            estimate: Optional VRAM estimate

        Returns:
            Formatted string with color codes
        """
        if status == CompatibilityStatus.FITS:
            return "[green]✓ Fits[/green]"
        elif status == CompatibilityStatus.TIGHT:
            headroom = f" ({estimate.headroom_percent:.0f}%)" if estimate else ""
            return f"[yellow]⚠ Tight{headroom}[/yellow]"
        elif status == CompatibilityStatus.TOO_LARGE:
            if estimate:
                over = estimate.estimated_vram_gb - estimate.available_vram_gb
                return f"[red]✗ Too large (+{over:.1f}GB)[/red]"
            return "[red]✗ Too large[/red]"
        elif status == CompatibilityStatus.CPU_ONLY:
            return "[cyan]ℹ CPU only[/cyan]"
        else:
            return "[dim]? Unknown[/dim]"
