"""Hardware detection and system information."""

from dataclasses import dataclass

import psutil
import torch


@dataclass
class GPUMemory:
    """GPU memory information."""

    total_bytes: int
    available_bytes: int
    used_bytes: int

    @property
    def total_gb(self) -> float:
        """Total memory in GB."""
        return self.total_bytes / (1024**3)

    @property
    def available_gb(self) -> float:
        """Available memory in GB."""
        return self.available_bytes / (1024**3)

    @property
    def used_gb(self) -> float:
        """Used memory in GB."""
        return self.used_bytes / (1024**3)


@dataclass
class GPUInfo:
    """GPU device information."""

    name: str
    compute_capability: tuple[int, int] | None
    memory: GPUMemory
    index: int


@dataclass
class DeviceInfo:
    """Complete system device information."""

    device_type: str  # cuda, mps, cpu
    cuda_available: bool
    cuda_version: str | None
    mps_available: bool
    gpus: list[GPUInfo]
    cpu_model: str
    cpu_cores: int
    cpu_threads: int
    ram_total_bytes: int
    ram_available_bytes: int
    pytorch_version: str
    pytorch_cuda_version: str | None

    @property
    def ram_total_gb(self) -> float:
        """Total RAM in GB."""
        return self.ram_total_bytes / (1024**3)

    @property
    def ram_available_gb(self) -> float:
        """Available RAM in GB."""
        return self.ram_available_bytes / (1024**3)


class HardwareDetector:
    """Detect and report hardware capabilities."""

    def detect(self) -> DeviceInfo:
        """Detect all hardware information.

        Returns:
            DeviceInfo object with complete system information.
        """
        cuda_available = torch.cuda.is_available()
        gpus = []

        if cuda_available:
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                memory = GPUMemory(
                    total_bytes=props.total_memory,
                    available_bytes=self._get_available_vram(i),
                    used_bytes=torch.cuda.memory_allocated(i),
                )
                gpus.append(
                    GPUInfo(
                        name=props.name,
                        compute_capability=(props.major, props.minor),
                        memory=memory,
                        index=i,
                    )
                )

        vm = psutil.virtual_memory()

        return DeviceInfo(
            device_type=self._get_device_type(),
            cuda_available=cuda_available,
            cuda_version=torch.version.cuda if cuda_available else None,
            mps_available=hasattr(torch.backends, "mps") and torch.backends.mps.is_available(),
            gpus=gpus,
            cpu_model=self._get_cpu_model(),
            cpu_cores=psutil.cpu_count(logical=False) or 0,
            cpu_threads=psutil.cpu_count(logical=True) or 0,
            ram_total_bytes=vm.total,
            ram_available_bytes=vm.available,
            pytorch_version=torch.__version__,
            pytorch_cuda_version=torch.version.cuda,
        )

    def recommend_models(self, available_vram_gb: float) -> list[str]:
        """Recommend model sizes based on available VRAM.

        Args:
            available_vram_gb: Available VRAM in gigabytes.

        Returns:
            List of recommendations.
        """
        if available_vram_gb >= 8:
            return ["large models (up to 8B parameters)", "full precision models"]
        elif available_vram_gb >= 4:
            return ["medium models (up to 3B parameters)", "FP16 for larger models"]
        elif available_vram_gb >= 2:
            return ["small models (up to 1B parameters)", "quantized models recommended"]
        else:
            return ["tiny models (<1B parameters)", "CPU mode recommended"]

    def can_run_model(self, model_size_gb: float) -> tuple[bool, str]:
        """Check if a model of given size can run on current hardware.

        Args:
            model_size_gb: Estimated model size in gigabytes.

        Returns:
            Tuple of (can_run, message).
        """
        info = self.detect()

        if info.cuda_available and info.gpus:
            available_vram = info.gpus[0].memory.available_gb
            # Model needs roughly 1.2x its size in memory for inference
            required = model_size_gb * 1.2

            if available_vram >= required:
                return True, f"✓ Model should fit in VRAM ({available_vram:.1f}GB available)"
            else:
                return (
                    False,
                    f"✗ Insufficient VRAM: need ~{required:.1f}GB, have {available_vram:.1f}GB",
                )

        # Check if it can run on CPU (RAM)
        available_ram = info.ram_available_gb
        required = model_size_gb * 1.5  # CPU needs more overhead

        if available_ram >= required:
            return True, f"⚠ Will run on CPU (slower, {available_ram:.1f}GB RAM available)"
        else:
            return (
                False,
                f"✗ Insufficient RAM: need ~{required:.1f}GB, have {available_ram:.1f}GB",
            )

    def _get_device_type(self) -> str:
        """Get the default device type."""
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"

    def _get_available_vram(self, device_id: int) -> int:
        """Get available VRAM for a device.

        Args:
            device_id: GPU device index.

        Returns:
            Available VRAM in bytes.
        """
        torch.cuda.empty_cache()
        free, _ = torch.cuda.mem_get_info(device_id)
        return free

    def _get_cpu_model(self) -> str:
        """Get CPU model name.

        Returns:
            CPU model string.
        """
        try:
            import cpuinfo

            info = cpuinfo.get_cpu_info()
            return info.get("brand_raw", "Unknown CPU")
        except Exception:
            # Fallback if py-cpuinfo fails
            return "Unknown CPU"
