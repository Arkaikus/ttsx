# TTX Architecture Documentation

## Overview

TTX is designed as a modular, extensible CLI tool for text-to-speech generation and model management. The architecture follows clean separation of concerns with a focus on maintainability and testability.

## Design Philosophy

### Core Principles

1. **Simplicity First**: Start simple, add complexity only when needed
2. **User-Centric**: CLI UX is paramount - fast feedback, clear messages
3. **Modular Design**: Each component has a single responsibility
4. **Testability**: All components can be tested in isolation
5. **Extensibility**: Easy to add new models and features
6. **Performance**: Lazy loading, caching, efficient operations

### Inspired By

- **uv**: Fast, reliable, great UX for package management
- **rye**: Modern Python project management
- **transformers CLI**: Model management patterns
- **huggingface-cli**: Hub integration

## Data Modeling Philosophy 🔴 CRITICAL

### Use Upstream Types When Available

**Prefer upstream types over duplication**. Only create our own models for domain-specific data.

### Pydantic for Domain-Specific Models

**All data structures use Pydantic models, NOT dataclasses**. This is a non-negotiable architectural decision.

**Rationale**:
1. **Validation**: Automatic validation with type checking at runtime
2. **Serialization**: Built-in JSON serialization for registry/config persistence
3. **Type Safety**: Runtime type checking with automatic coercion
4. **Documentation**: Field descriptions embedded in the schema
5. **Consistency**: Unified approach across configuration and data models
6. **Future-proof**: Easy to add validation rules, computed fields, and serialization logic

**Where Pydantic is used**:
- ✅ `config.py` - `TTXConfig` (extends `pydantic-settings.BaseSettings`)
- ✅ `models/types.py` - `ModelInfo`, `InstalledModel`
- Future: API request/response models
- Future: Generation parameters and audio settings
- Future: Voice profiles and embeddings metadata

**Example Pattern**:
```python
from pydantic import BaseModel, Field, computed_field
from typing import Optional

class ModelInfo(BaseModel):
    """Model information with automatic validation."""
    
    # Required fields with validation
    model_id: str = Field(..., description="Full model ID (author/name)")
    downloads: int = Field(default=0, ge=0, description="Download count")
    
    # Optional fields with constraints
    size_bytes: Optional[int] = Field(None, ge=0, description="Model size")
    
    # Configuration
    model_config = {"frozen": False}  # Allow field updates
    
    # Computed properties (don't store, calculate on access)
    @computed_field  # type: ignore[misc]
    @property
    def size_gb(self) -> Optional[float]:
        """Size in gigabytes (computed)."""
        return self.size_bytes / (1024**3) if self.size_bytes else None
    
    # Helper methods
    def format_size(self) -> str:
        """Human-readable size string."""
        if not self.size_bytes:
            return "Unknown"
        gb = self.size_gb
        return f"{gb:.1f} GB" if gb and gb >= 1 else f"{self.size_bytes / 1024**2:.0f} MB"
```

**DON'T use dataclasses** for any models that need:
- JSON serialization (registry, config files)
- Runtime validation
- Type coercion
- Field constraints (min/max, regex, custom validators)

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                            │
│  (typer + rich: command parsing, validation, output)        │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────────────┐
│                    Application Layer                         │
│  (business logic, orchestration, error handling)            │
├──────────────────┬──────────────┬──────────────┬────────────┤
│  Model Manager   │  Generator   │  Voice       │  Cache     │
│                  │  Engine      │  Cloning     │  Manager   │
└──────────────────┴──────────────┴──────────────┴────────────┘
                   │
┌──────────────────┴──────────────────────────────────────────┐
│                    Infrastructure Layer                      │
│  (HF Hub API, file system, PyTorch, audio processing)       │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow: Text → Speech

```
User Input → CLI Parser → Text Processor → Model Loader
                                              ↓
Audio File ← Audio Writer ← Post-Processor ← TTS Engine
```

## Module Architecture

### 1. CLI Module (`cli.py`)

**Responsibility**: Command-line interface and user interaction

**Key Components**:
- Command definitions using Typer
- Argument parsing and validation
- Output formatting with Rich
- Progress reporting
- Error display

**Design Notes**:
- Thin layer - no business logic
- Delegate all work to application layer
- Focus on user experience
- Handle Ctrl+C gracefully

```python
# Example structure
import typer
from rich.console import Console

app = typer.Typer()
console = Console()

@app.command()
def generate(
    text: str,
    model: str = "qwen3-tts",
    output: Optional[Path] = None,
):
    """Generate speech from text"""
    try:
        # Delegate to application layer
        result = SpeechGenerator().generate(text, model, output)
        console.print(f"[green]✓[/green] Generated: {result}")
    except TTXError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
```

### 2. Models Module (`models/`)

**Responsibility**: Model discovery, download, storage, and loading

#### 2.1 Hub Integration (`hub.py`)

```python
class HuggingFaceHub:
    """Interface to HuggingFace model hub"""
    
    def search_models(
        self,
        query: str = "",
        pipeline_tag: str = "text-to-speech",
        library: str = "pytorch",
    ) -> list[ModelInfo]:
        """Search for models on HuggingFace Hub"""
        
    def get_model_info(self, model_id: str) -> ModelInfo:
        """Get detailed model information"""
        
    def download_model(
        self,
        model_id: str,
        cache_dir: Path,
        progress_callback: Optional[Callable] = None,
    ) -> Path:
        """Download model to local cache"""
```

**Design Notes**:
- Use `huggingface_hub` library for API access
- Implement rate limiting and retries
- Support authentication for gated models
- Cache API responses when appropriate

#### 2.2 Model Registry (`registry.py`)

```python
class ModelRegistry:
    """Track installed models and metadata"""
    
    def register(self, model_id: str, path: Path, metadata: ModelInfo):
        """Register a newly installed model"""
        
    def get(self, model_id: str) -> Optional[ModelEntry]:
        """Get registered model information"""
        
    def list_all(self) -> list[ModelEntry]:
        """List all installed models"""
        
    def remove(self, model_id: str):
        """Unregister and optionally delete model"""
```

**Storage**: JSON file at `~/.ttx/models/registry.json`

```json
{
  "models": [
    {
      "id": "Qwen/Qwen3-TTS-12Hz-1.7B",
      "path": "/home/user/.ttx/models/qwen3-tts",
      "installed_at": "2026-02-16T12:00:00Z",
      "size_bytes": 1700000000,
      "last_used": "2026-02-16T13:30:00Z",
      "metadata": {
        "pipeline_tag": "text-to-speech",
        "languages": ["en", "zh"],
        "sample_rate": 12000
      }
    }
  ]
}
```

#### 2.3 Model Loader (`loader.py`)

```python
class ModelLoader:
    """Load and initialize TTS models"""
    
    def load(
        self,
        model_id: str,
        device: str = "auto",
    ) -> TTSModel:
        """Load model into memory"""
        
    def unload(self, model_id: str):
        """Free model from memory"""
```

**Design Notes**:
- Implement model adapter pattern for different architectures
- Support device selection (cpu, cuda, mps)
- Lazy loading - only load when needed
- Model pooling for server mode (future)

### 3. Generation Module (`generation/`)

**Responsibility**: Convert text to speech using loaded models

#### 3.1 Text Processing (`processors.py`)

```python
class TextProcessor:
    """Preprocess text before TTS generation"""
    
    def normalize(self, text: str) -> str:
        """Normalize text (unicode, punctuation, etc.)"""
        
    def segment(self, text: str) -> list[str]:
        """Split long text into manageable chunks"""
        
    def expand_abbreviations(self, text: str) -> str:
        """Expand common abbreviations (Dr. → Doctor)"""
```

**Features**:
- Text normalization
- Sentence segmentation
- Number expansion (123 → one hundred twenty-three)
- Abbreviation expansion
- Language detection (future)

#### 3.2 Generation Engine (`engine.py`)

```python
class TTSEngine:
    """Core text-to-speech generation"""
    
    def __init__(self, model_loader: ModelLoader):
        self.loader = model_loader
        self._loaded_models: dict[str, TTSModel] = {}
    
    def generate(
        self,
        text: str,
        model_id: str,
        voice_embedding: Optional[np.ndarray] = None,
        **kwargs,
    ) -> AudioOutput:
        """Generate speech from text"""
        
    def batch_generate(
        self,
        texts: list[str],
        model_id: str,
        **kwargs,
    ) -> list[AudioOutput]:
        """Generate speech for multiple texts efficiently"""
```

**Design Notes**:
- Model-agnostic interface
- Support streaming for long texts (future)
- GPU memory management
- Error recovery for batch processing

#### 3.3 Audio Processing (`audio.py`)

```python
class AudioProcessor:
    """Post-process generated audio"""
    
    def normalize_volume(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio volume"""
        
    def trim_silence(
        self,
        audio: np.ndarray,
        threshold: float = 0.01,
    ) -> np.ndarray:
        """Remove leading/trailing silence"""
        
    def save(
        self,
        audio: np.ndarray,
        path: Path,
        sample_rate: int,
        format: str = "wav",
    ):
        """Save audio to file"""
```

### 4. Voice Module (`voice/`)

**Responsibility**: Voice cloning and profile management

#### 4.1 Voice Encoder (`encoder.py`)

```python
class VoiceEncoder:
    """Extract voice embeddings from audio samples"""
    
    def encode(self, audio_path: Path) -> VoiceEmbedding:
        """Extract voice embedding from reference audio"""
        
    def validate_sample(self, audio_path: Path) -> bool:
        """Check if audio sample is suitable for cloning"""
```

**Requirements**:
- Support multiple audio formats (WAV, MP3, FLAC)
- Validate sample quality (duration, SNR, sample rate)
- Efficient embedding extraction

#### 4.2 Voice Profiles (`profiles.py`)

```python
class VoiceProfileManager:
    """Manage saved voice profiles"""
    
    def save_profile(
        self,
        name: str,
        embedding: VoiceEmbedding,
        metadata: dict,
    ):
        """Save a voice profile for reuse"""
        
    def load_profile(self, name: str) -> VoiceEmbedding:
        """Load a saved voice profile"""
        
    def list_profiles(self) -> list[str]:
        """List all saved profiles"""
```

**Storage**: `~/.ttx/voices/`
```
voices/
├── alice.json
├── bob.json
└── narrator.json
```

### 5. Configuration Module (`config.py`)

**Responsibility**: Manage user configuration and settings

```python
from pydantic_settings import BaseSettings

class TTXConfig(BaseSettings):
    """Global configuration"""
    
    cache_dir: Path = Path.home() / ".ttx" / "models"
    max_cache_size: str = "10GB"
    default_model: str = "qwen3-tts"
    device: str = "auto"
    sample_rate: int = 22050
    audio_format: str = "wav"
    
    class Config:
        env_prefix = "TTX_"
        env_file = ".env"

# Singleton instance
config = TTXConfig()
```

**Configuration Sources** (priority order):
1. Command-line arguments
2. Environment variables (`TTX_*`)
3. User config file (`~/.ttx/config.toml`)
4. Default values

### 6. Cache Module (`cache.py`)

**Responsibility**: Manage local model storage

```python
class CacheManager:
    """Manage model cache with size limits and eviction"""
    
    def __init__(self, cache_dir: Path, max_size: int):
        self.cache_dir = cache_dir
        self.max_size = max_size
    
    def get_size(self) -> int:
        """Get current cache size in bytes"""
        
    def ensure_space(self, required: int):
        """Ensure sufficient space, evict if needed"""
        
    def evict_lru(self, size: int):
        """Evict least recently used models"""
```

**Eviction Strategy**:
- LRU (Least Recently Used) by default
- Respect pinned models (user can pin favorites)
- Configurable max size
- Atomic operations (temp files → rename)

## Hardware Detection and Compatibility

### Hardware Module (`hardware.py`)

**Current Implementation**: Detects system hardware capabilities

**Purpose**: Provide comprehensive hardware information to help users understand their system capabilities and choose appropriate models.

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class GPUMemory:
    """GPU memory information"""
    total_bytes: int
    available_bytes: int
    used_bytes: int
    
    @property
    def total_gb(self) -> float:
        return self.total_bytes / (1024**3)
    
    @property
    def available_gb(self) -> float:
        return self.available_bytes / (1024**3)

@dataclass
class GPUInfo:
    """GPU information"""
    name: str
    compute_capability: Optional[tuple[int, int]]
    memory: GPUMemory
    index: int

@dataclass
class DeviceInfo:
    """Complete device information"""
    device_type: str  # cuda, mps, cpu
    cuda_available: bool
    cuda_version: Optional[str]
    mps_available: bool
    gpus: list[GPUInfo]
    cpu_model: str
    cpu_cores: int
    cpu_threads: int
    ram_total_bytes: int
    ram_available_bytes: int
    pytorch_version: str
    pytorch_cuda_version: Optional[str]

class HardwareDetector:
    """Detect and report hardware capabilities"""
    
    def detect(self) -> DeviceInfo:
        """Detect all hardware information"""
        import torch
        import psutil
        
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
                gpus.append(GPUInfo(
                    name=props.name,
                    compute_capability=(props.major, props.minor),
                    memory=memory,
                    index=i,
                ))
        
        return DeviceInfo(
            device_type=self._get_device_type(),
            cuda_available=cuda_available,
            cuda_version=torch.version.cuda if cuda_available else None,
            mps_available=torch.backends.mps.is_available(),
            gpus=gpus,
            cpu_model=self._get_cpu_model(),
            cpu_cores=psutil.cpu_count(logical=False),
            cpu_threads=psutil.cpu_count(logical=True),
            ram_total_bytes=psutil.virtual_memory().total,
            ram_available_bytes=psutil.virtual_memory().available,
            pytorch_version=torch.__version__,
            pytorch_cuda_version=torch.version.cuda,
        )
    
    def recommend_models(self, available_vram_gb: float) -> list[str]:
        """Recommend models based on available VRAM"""
        if available_vram_gb >= 8:
            return ["large models (up to 8B parameters)"]
        elif available_vram_gb >= 4:
            return ["medium models (up to 3B parameters)"]
        elif available_vram_gb >= 2:
            return ["small models (up to 1B parameters)"]
        else:
            return ["tiny models (<1B) or use CPU"]
    
    def _get_available_vram(self, device_id: int) -> int:
        """Get available VRAM for device"""
        import torch
        torch.cuda.empty_cache()
        # Get free memory
        return torch.cuda.mem_get_info(device_id)[0]
```

**CLI Command**:

```python
@app.command()
def hw():
    """Display hardware information and capabilities.
    
    Shows GPU, CPU, and memory information relevant for TTS model selection.
    """
    from ttx.hardware import HardwareDetector
    from rich.table import Table
    from rich.panel import Panel
    
    detector = HardwareDetector()
    info = detector.detect()
    
    # Display compute info
    compute_table = Table(title="Compute", show_header=False)
    compute_table.add_column("Property", style="cyan")
    compute_table.add_column("Value", style="white")
    
    if info.cuda_available:
        compute_table.add_row("Device", "CUDA GPU")
        for gpu in info.gpus:
            compute_table.add_row("GPU Model", gpu.name)
            compute_table.add_row("GPU Index", str(gpu.index))
            compute_table.add_row(
                "VRAM",
                f"{gpu.memory.total_gb:.1f} GB total / "
                f"{gpu.memory.available_gb:.1f} GB available"
            )
        compute_table.add_row("CUDA Version", info.cuda_version or "N/A")
    elif info.mps_available:
        compute_table.add_row("Device", "Apple Metal (MPS)")
    else:
        compute_table.add_row("Device", "CPU only")
        compute_table.add_row(
            "⚠️  GPU",
            "[yellow]No GPU detected - generation will be slower[/yellow]"
        )
    
    # Display CPU info
    cpu_table = Table(title="CPU", show_header=False)
    cpu_table.add_column("Property", style="cyan")
    cpu_table.add_column("Value", style="white")
    cpu_table.add_row("Model", info.cpu_model)
    cpu_table.add_row(
        "Cores",
        f"{info.cpu_cores} physical / {info.cpu_threads} logical"
    )
    cpu_table.add_row(
        "RAM",
        f"{info.ram_total_bytes / (1024**3):.1f} GB total / "
        f"{info.ram_available_bytes / (1024**3):.1f} GB available"
    )
    
    # Display software info
    sw_table = Table(title="Software", show_header=False)
    sw_table.add_row("PyTorch", info.pytorch_version)
    sw_table.add_row("Build", f"CUDA {info.pytorch_cuda_version}" if info.pytorch_cuda_version else "CPU")
    sw_table.add_row("Default Device", info.device_type)
    
    console.print(compute_table)
    console.print(cpu_table)
    console.print(sw_table)
    
    # Recommendations
    if info.cuda_available and info.gpus:
        vram_gb = info.gpus[0].memory.available_gb
        recommendations = detector.recommend_models(vram_gb)
        
        console.print("\n[bold]Recommendations[/bold]")
        console.print(f"  ✓ Your hardware can run {recommendations[0]}")
        console.print("  ✓ GPU acceleration available")
        if vram_gb < 8:
            console.print("  ℹ Consider using quantized models for better fit")
```

**Dependencies**:
```toml
dependencies = [
    # ... existing
    "psutil>=6.1.0",  # System and process utilities
    "py-cpuinfo>=9.0.0",  # Detailed CPU information
]
```

### Hardware Requirements Module (`hardware_requirements.py`)

**Purpose**: Calculate model hardware requirements and compatibility.

**VRAM Overhead Calculation**:

Models need more VRAM than their file size due to:
- Activation tensors during inference
- KV cache for attention mechanisms  
- Temporary buffers and intermediate results
- Framework overhead

**Overhead Multipliers** (based on precision):
```python
PRECISION_MULTIPLIERS = {
    "fp32": 1.5,  # Full precision (32-bit floats)
    "fp16": 1.2,  # Half precision (16-bit floats) - RECOMMENDED
    "int8": 1.1,  # Quantized (8-bit integers)
}
```

**Example Calculations**:
| Model Size | Precision | Overhead | Required VRAM | Safety Buffer (20%) | Total |
|------------|-----------|----------|---------------|---------------------|-------|
| 1.7 GB     | FP16      | 1.2x     | 2.04 GB       | +0.41 GB           | 2.45 GB |
| 3.4 GB     | FP16      | 1.2x     | 4.08 GB       | +0.82 GB           | 4.90 GB |
| 7.0 GB     | FP16      | 1.2x     | 8.40 GB       | +1.68 GB           | 10.08 GB |

**Compatibility Status Enum**:
```python
from enum import Enum

class CompatibilityStatus(str, Enum):
    """Model compatibility with current hardware."""
    
    FITS = "fits"          # Green: Model < 70% of available VRAM
    TIGHT = "tight"        # Yellow: Model 70-95% of available VRAM
    TOO_LARGE = "too_large"  # Red: Model > 95% of available VRAM
    UNKNOWN = "unknown"    # Gray: Model size not available
```

**Implementation**:
```python
from dataclasses import dataclass
from typing import Literal, Optional

@dataclass
class VRAMRequirement:
    """VRAM requirements for different precisions."""
    fp32_gb: float
    fp16_gb: float
    int8_gb: float
    recommended_precision: str

class HardwareRequirements:
    """Calculate and check model hardware requirements."""
    
    PRECISION_MULTIPLIERS = {
        "fp32": 1.5,
        "fp16": 1.2,
        "int8": 1.1,
    }
    
    SAFETY_MARGIN = 0.2  # Keep 20% VRAM free
    
    @classmethod
    def estimate_vram_needed(
        cls,
        model_size_bytes: int,
        precision: Literal["fp32", "fp16", "int8"] = "fp16",
        safety_margin: float = SAFETY_MARGIN,
    ) -> float:
        """Estimate VRAM needed for model inference.
        
        Args:
            model_size_bytes: Model size on disk in bytes
            precision: Inference precision
            safety_margin: Extra buffer (0.2 = 20% buffer)
        
        Returns:
            Estimated VRAM needed in GB
        """
        multiplier = cls.PRECISION_MULTIPLIERS[precision]
        
        # Model size in GB
        model_gb = model_size_bytes / (1024**3)
        
        # Apply overhead multiplier
        base_required = model_gb * multiplier
        
        # Add safety margin
        total_required = base_required * (1 + safety_margin)
        
        return total_required
    
    @classmethod
    def get_vram_requirements(
        cls, model_size_bytes: int
    ) -> VRAMRequirement:
        """Get VRAM requirements for all precisions.
        
        Args:
            model_size_bytes: Model size in bytes
        
        Returns:
            VRAMRequirement with estimates for each precision
        """
        return VRAMRequirement(
            fp32_gb=cls.estimate_vram_needed(model_size_bytes, "fp32"),
            fp16_gb=cls.estimate_vram_needed(model_size_bytes, "fp16"),
            int8_gb=cls.estimate_vram_needed(model_size_bytes, "int8"),
            recommended_precision="fp16",
        )
    
    @classmethod
    def can_run_on_hardware(
        cls,
        model_size_bytes: int,
        available_vram_gb: float,
        precision: str = "fp16",
    ) -> tuple[bool, str, CompatibilityStatus]:
        """Check if model can run on current hardware.
        
        Args:
            model_size_bytes: Model size in bytes
            available_vram_gb: Available VRAM in GB
            precision: Target precision
        
        Returns:
            Tuple of (can_run, message, status)
        """
        required_gb = cls.estimate_vram_needed(model_size_bytes, precision)
        usage_ratio = required_gb / available_vram_gb if available_vram_gb > 0 else 999
        
        # Determine status based on thresholds
        if usage_ratio <= 0.7:
            status = CompatibilityStatus.FITS
            can_run = True
            msg = f"✓ Will fit comfortably ({required_gb:.1f}GB / {available_vram_gb:.1f}GB)"
        elif usage_ratio <= 0.95:
            status = CompatibilityStatus.TIGHT
            can_run = True
            msg = f"⚠ Tight fit ({required_gb:.1f}GB / {available_vram_gb:.1f}GB) - may cause OOM"
        else:
            status = CompatibilityStatus.TOO_LARGE
            can_run = False
            msg = f"✗ Too large ({required_gb:.1f}GB needed, {available_vram_gb:.1f}GB available)"
        
        return can_run, msg, status
    
    @classmethod
    def find_quantized_versions(
        cls, model_id: str, hub: "HuggingFaceHub"
    ) -> list["ModelInfo"]:
        """Search for quantized versions of a model.
        
        Args:
            model_id: Base model ID
            hub: HuggingFace Hub client
        
        Returns:
            List of quantized model variants
        """
        # Extract base name without org
        base_name = model_id.split("/")[-1]
        
        # Common quantization patterns
        patterns = [
            f"{base_name}-GPTQ",
            f"{base_name}-gptq",
            f"{base_name}-4bit",
            f"{base_name}-8bit",
            f"{base_name}-AWQ",
            f"{base_name}-awq",
            f"{base_name}-GGUF",
            f"{base_name}-gguf",
            f"{base_name}-int8",
            f"{base_name}-int4",
        ]
        
        quantized = []
        for pattern in patterns:
            try:
                results = hub.search_models(query=pattern, limit=5)
                quantized.extend(results)
            except Exception:
                continue
        
        # Remove duplicates and sort by size
        seen = set()
        unique_quantized = []
        for model in quantized:
            if model.model_id not in seen:
                seen.add(model.model_id)
                unique_quantized.append(model)
        
        # Sort by size (smallest first)
        unique_quantized.sort(key=lambda m: m.size_bytes or float('inf'))
        
        return unique_quantized
```

**Integration with ModelInfo**:
```python
class ModelInfo(BaseModel):
    # ... existing fields ...
    
    @computed_field
    @property
    def compatibility(self) -> Optional[CompatibilityStatus]:
        """Compute compatibility with current hardware."""
        if not self.size_bytes:
            return CompatibilityStatus.UNKNOWN
        
        from ttx.hardware import HardwareDetector
        from ttx.hardware_requirements import HardwareRequirements
        
        detector = HardwareDetector()
        info = detector.detect()
        
        # CPU-only systems can run anything (just slower)
        if not info.cuda_available or not info.gpus:
            return None
        
        vram_gb = info.gpus[0].memory.available_gb
        _, _, status = HardwareRequirements.can_run_on_hardware(
            self.size_bytes, vram_gb
        )
        
        return status
    
    def get_hardware_warning(self) -> Optional[str]:
        """Get human-readable hardware warning if applicable."""
        if self.compatibility == CompatibilityStatus.TOO_LARGE:
            return (
                f"⚠ This model requires more VRAM than available. "
                f"Consider using a quantized version or running on CPU."
            )
        elif self.compatibility == CompatibilityStatus.TIGHT:
            return (
                f"⚠ This model may be tight. Close other GPU applications "
                f"or use FP16 precision."
            )
        return None
```

**Special Cases**:

1. **CPU-Only Systems**: 
   - Return `None` for compatibility (no VRAM constraints)
   - Show "Running on CPU - will be slower" message

2. **MPS (Apple Silicon)**:
   - Unified memory architecture
   - Check against RAM instead of VRAM
   - Different overhead characteristics

3. **Multiple GPUs**:
   - Use GPU with most available VRAM
   - Allow user to specify: `--device cuda:1`

4. **Unknown Model Size**:
   - Return `CompatibilityStatus.UNKNOWN`
   - Don't filter out of search results
   - Warn user that size check couldn't be performed

## Cross-Cutting Concerns

### Logging

**Strategy**: Structured logging with multiple levels

```python
import logging
from rich.logging import RichHandler

# Setup in __main__.py or cli.py
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)]
)

logger = logging.getLogger("ttx")
```

**Log Levels**:
- `DEBUG`: Detailed diagnostic info (model parameters, file paths)
- `INFO`: General progress messages (downloading, generating)
- `WARNING`: Recoverable issues (fallback to CPU, old config format)
- `ERROR`: Failures (model load error, invalid input)
- `CRITICAL`: System failures (out of disk space, corrupted cache)

### Error Handling

**Exception Hierarchy**:

```python
class TTXError(Exception):
    """Base exception"""

class ModelError(TTXError):
    """Model-related errors"""

class ModelNotFoundError(ModelError):
    """Model doesn't exist"""

class ModelDownloadError(ModelError):
    """Failed to download model"""

class GenerationError(TTXError):
    """Generation failed"""

class AudioError(TTXError):
    """Audio processing error"""

class ConfigError(TTXError):
    """Configuration error"""
```

**Error Handling Pattern**:
```python
try:
    model = loader.load(model_id)
except ModelNotFoundError as e:
    logger.error("Model not found: %s", model_id)
    console.print(
        f"[red]Error:[/red] Model '{model_id}' is not installed.\n"
        f"[yellow]Tip:[/yellow] Run [cyan]ttx install {model_id}[/cyan]"
    )
    raise typer.Exit(1)
```

### Progress Reporting

Use Rich progress for long operations:

```python
from rich.progress import Progress, SpinnerColumn, TextColumn

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    console=console,
) as progress:
    task = progress.add_task("Downloading model...", total=None)
    download_model(model_id, callback=lambda: progress.update(task))
```

## Data Models

### Model Information

```python
from pydantic import BaseModel

class ModelInfo(BaseModel):
    """Model metadata from HuggingFace"""
    id: str
    author: str
    pipeline_tag: str
    downloads: int
    likes: int
    languages: list[str]
    sample_rate: Optional[int] = None
    license: Optional[str] = None
    size_bytes: Optional[int] = None
    
class ModelEntry(BaseModel):
    """Installed model entry"""
    info: ModelInfo
    path: Path
    installed_at: datetime
    last_used: Optional[datetime] = None
    pinned: bool = False
```

### Audio Output

```python
class AudioOutput(BaseModel):
    """Generated audio output"""
    audio: np.ndarray
    sample_rate: int
    duration_seconds: float
    model_id: str
    text: str
    
    def save(self, path: Path, format: str = "wav"):
        """Save audio to file"""
```

### Voice Profile

```python
class VoiceEmbedding(BaseModel):
    """Voice embedding for cloning"""
    embedding: np.ndarray  # or list[float] for JSON serialization
    sample_rate: int
    source_file: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True

class VoiceProfile(BaseModel):
    """Saved voice profile"""
    name: str
    embedding: VoiceEmbedding
    created_at: datetime
    description: Optional[str] = None
    language: Optional[str] = None
```

## File System Layout

### User Directories

```
~/.ttx/
├── config.toml              # User configuration
├── models/
│   ├── registry.json        # Installed models database
│   ├── qwen3-tts/          # Model files
│   │   ├── config.json
│   │   ├── model.safetensors
│   │   └── tokenizer/
│   └── moss-tts/
├── voices/                  # Saved voice profiles
│   ├── alice.json
│   └── bob.json
├── cache/                   # Temporary files
└── logs/                    # Application logs
    └── ttx.log
```

### Project Structure

```
ttx/
├── src/ttx/
│   ├── __init__.py
│   ├── __main__.py          # Entry point: `python -m ttx`
│   ├── cli.py               # CLI commands
│   ├── config.py            # Configuration management
│   ├── cache.py             # Cache management
│   ├── hardware.py          # Hardware detection and info
│   │
│   ├── models/              # Model management
│   │   ├── __init__.py
│   │   ├── hub.py           # HF Hub API
│   │   ├── loader.py        # Model loading
│   │   ├── registry.py      # Installed models tracking
│   │   ├── types.py         # Model type definitions
│   │   └── adapters/        # Model-specific adapters
│   │       ├── __init__.py
│   │       ├── base.py      # Base adapter protocol
│   │       ├── qwen.py      # Qwen TTS models
│   │       └── moss.py      # MOSS TTS models
│   │
│   ├── generation/          # TTS generation
│   │   ├── __init__.py
│   │   ├── engine.py        # Generation orchestration
│   │   ├── processors.py   # Text preprocessing
│   │   └── audio.py         # Audio post-processing
│   │
│   ├── voice/               # Voice cloning
│   │   ├── __init__.py
│   │   ├── cloner.py        # Cloning logic
│   │   ├── encoder.py       # Voice encoding
│   │   └── profiles.py      # Profile management
│   │
│   └── utils/               # Utilities
│       ├── __init__.py
│       ├── logger.py        # Logging setup
│       ├── progress.py      # Progress reporting
│       ├── validators.py    # Input validation
│       └── exceptions.py    # Custom exceptions
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Pytest configuration
│   ├── unit/                # Unit tests
│   │   ├── test_hub.py
│   │   ├── test_loader.py
│   │   └── test_engine.py
│   ├── integration/         # Integration tests
│   │   └── test_cli.py
│   └── fixtures/            # Test fixtures
│       ├── audio/
│       └── models/
│
├── docs/                    # User documentation
├── pyproject.toml
├── uv.lock
├── README.md
├── TODO.md
├── AGENTS.md
└── ARCHITECTURE.md
```

## Design Patterns

### 1. Async/Await Pattern

**All I/O-bound operations use asyncio for concurrency and responsiveness.**

#### Implementation

```python
# 1. Async helper functions (models/types.py)
async def get_model_size_async(model: ModelInfo) -> Optional[int]:
    """Non-blocking size fetch using thread pool executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: get_model_size(model, fetch_accurate=True)
    )

# 2. Async command implementation (commands/search.py)
async def search_command_async(query: Optional[str], limit: int) -> None:
    """Async search with concurrent size fetching."""
    # Fetch models list (fast)
    models = list(hub.search_models(query, limit))
    
    # Create table with "Loading..." for sizes
    table = create_table_with_loading(models)
    
    # Fetch sizes concurrently with live updates
    async def fetch_and_update_size(idx, model):
        try:
            size = await get_model_size_async(model)
            return (idx, format_model_size(size))
        except Exception:
            return (idx, "[red]Error[/red]")
    
    fetch_tasks = [fetch_and_update_size(i, m) for i, m in enumerate(models)]
    
    # Update table as each size completes
    with Live(table, refresh_per_second=4) as live:
        for coro in asyncio.as_completed(fetch_tasks):
            idx, size_str = await coro
            update_table_row(table, idx, size_str)
            live.update(table)

# 3. Sync wrapper for Typer (commands/search.py)
def search_command(query: Optional[str] = None, limit: int = 20) -> None:
    """Sync wrapper that runs async implementation."""
    asyncio.run(search_command_async(query=query, limit=limit))
```

#### Performance

- ✅ **10 models**: ~4.5 seconds total
- ✅ **5 models**: ~4.2 seconds total
- ✅ **2 models**: ~4.0 seconds total
- All operations run concurrently using `asyncio.as_completed()`

#### Benefits

1. **Non-blocking I/O**: Main thread stays responsive
2. **Concurrent fetching**: N API calls in parallel
3. **Progressive updates**: Results appear as they arrive
4. **Better UX**: No waiting for all data before showing anything
5. **Scalable**: Handles 10+ models efficiently

### 2. Adapter Pattern (Model Compatibility)

Different TTS models have different APIs. Use adapters to provide uniform interface.

```python
from typing import Protocol

class TTSAdapter(Protocol):
    """Protocol for TTS model adapters"""
    
    def load_model(self, path: Path) -> Any:
        """Load model from disk"""
        ...
    
    def generate(
        self,
        text: str,
        voice_embedding: Optional[np.ndarray] = None,
        **kwargs,
    ) -> np.ndarray:
        """Generate audio from text"""
        ...
    
    def get_sample_rate(self) -> int:
        """Get model's native sample rate"""
        ...

class Qwen3Adapter:
    """Adapter for Qwen3 TTS models"""
    
    def load_model(self, path: Path):
        from transformers import AutoModel
        return AutoModel.from_pretrained(path)
    
    def generate(self, text: str, **kwargs) -> np.ndarray:
        # Qwen3-specific generation logic
        ...

# Factory function
def get_adapter(model_id: str) -> TTSAdapter:
    if "qwen" in model_id.lower():
        return Qwen3Adapter()
    elif "moss" in model_id.lower():
        return MOSSAdapter()
    else:
        raise ValueError(f"Unknown model family: {model_id}")
```

### 3. Repository Pattern (Data Access)

Separate data access from business logic.

```python
class ModelRepository:
    """Abstract model storage"""
    
    def __init__(self, hub: HuggingFaceHub, registry: ModelRegistry):
        self.hub = hub
        self.registry = registry
    
    def find_by_id(self, model_id: str) -> Optional[ModelEntry]:
        """Find model locally or remotely"""
        # Check local first
        local = self.registry.get(model_id)
        if local:
            return local
        # Check remote
        return self.hub.get_model_info(model_id)
    
    def install(self, model_id: str) -> ModelEntry:
        """Download and register model"""
        ...
```

### 4. Builder Pattern (Complex Object Construction)

For building generation requests with many options.

```python
class GenerationRequest:
    """Builder for TTS generation requests"""
    
    def __init__(self):
        self._text: Optional[str] = None
        self._model_id: Optional[str] = None
        self._voice_sample: Optional[Path] = None
        self._options: dict = {}
    
    def with_text(self, text: str) -> "GenerationRequest":
        self._text = text
        return self
    
    def with_model(self, model_id: str) -> "GenerationRequest":
        self._model_id = model_id
        return self
    
    def with_voice(self, sample: Path) -> "GenerationRequest":
        self._voice_sample = sample
        return self
    
    def build(self) -> dict:
        """Validate and return request dict"""
        if not self._text:
            raise ValueError("Text is required")
        if not self._model_id:
            raise ValueError("Model is required")
        return {
            "text": self._text,
            "model_id": self._model_id,
            "voice_sample": self._voice_sample,
            **self._options,
        }
```

### 5. Strategy Pattern (Algorithm Selection)

Different generation strategies for different use cases.

```python
class GenerationStrategy(Protocol):
    """Strategy for TTS generation"""
    def execute(self, request: dict) -> AudioOutput: ...

class StandardGeneration(GenerationStrategy):
    """Standard single-text generation"""
    ...

class BatchGeneration(GenerationStrategy):
    """Optimized batch generation"""
    ...

class StreamingGeneration(GenerationStrategy):
    """Streaming for long texts"""
    ...
```

## Dependency Management

### Why uv?

1. **Speed**: 10-100x faster than pip
2. **Reliability**: Better dependency resolution
3. **Modern**: Built for Python 3.14+
4. **Compatibility**: Works with standard pyproject.toml

### Managing Dependencies

```bash
# Add dependency
uv add torch transformers

# Add dev dependency
uv add --dev pytest ruff

# Update dependencies
uv lock --upgrade

# Install for development
uv pip install -e ".[dev]"
```

### Dependency Categories

**Core** (required for basic functionality):
- torch, torchaudio
- transformers
- huggingface-hub
- typer, rich
- soundfile

**Optional** (for advanced features):
- librosa (advanced audio processing)
- pydub (format conversion)
- faster-whisper (audio preprocessing)

**Development**:
- pytest, pytest-cov
- ruff, mypy
- pytest-mock

## Performance Considerations

### Model Loading
- **Lazy Loading**: Only load model when first generation is requested
- **Memory Management**: Unload models when not in use (optional)
- **GPU Optimization**: Use torch.compile() for 3.14+ (future)

### Caching Strategy
1. **API Response Caching**: Cache HF Hub search results (5 min TTL)
2. **Model Caching**: Persistent local storage
3. **Voice Embedding Caching**: Cache encoded voice samples
4. **Generated Audio Caching**: Optional for repeated generations

### Batch Processing
- Process multiple texts in parallel
- Use GPU batch processing when available
- Stream results as they complete
- Graceful degradation on errors

## Security Considerations

### 1. Model Integrity
- Verify checksums after download
- Use HuggingFace's trust mechanisms
- Warn about unverified models

### 2. Input Validation
- Sanitize text input (prevent injection)
- Validate file paths (prevent directory traversal)
- Limit text length (prevent DoS)

### 3. Credentials
- Store HF tokens securely (use keyring library)
- Never log tokens
- Support token from environment variable

### 4. Sandboxing
- Consider running model inference in subprocess (future)
- Limit file system access for models
- Resource limits for generation (timeout, memory)

## Scalability & Extensibility

### Adding New Models

1. Create adapter in `models/adapters/`
2. Implement `TTSAdapter` protocol
3. Register in factory function
4. Add tests
5. Document in README

### Adding New Commands

1. Add command function in `cli.py`
2. Implement logic in appropriate module
3. Add tests
4. Update documentation

### Plugin System (Future)

```python
# Future: Support custom model adapters
class PluginManager:
    def register_adapter(self, pattern: str, adapter_class: type):
        """Register custom model adapter"""
        
    def load_plugins(self, plugin_dir: Path):
        """Load plugins from directory"""
```

## Testing Strategy

### Unit Tests
- Test each module independently
- Mock external dependencies (HF Hub, file I/O, PyTorch)
- Focus on edge cases and error conditions
- Target 80%+ coverage

### Integration Tests
- Test CLI commands end-to-end
- Use small test models or fixtures
- Test model download and caching
- Test full generation pipeline

### Fixtures
```python
# tests/conftest.py
import pytest

@pytest.fixture
def mock_model_info():
    """Mock model metadata"""
    return ModelInfo(
        id="test/model",
        author="test",
        pipeline_tag="text-to-speech",
        downloads=100,
        likes=10,
        languages=["en"],
    )

@pytest.fixture
def test_audio_sample(tmp_path):
    """Create test audio file"""
    audio_path = tmp_path / "test.wav"
    # Generate silent audio
    ...
    return audio_path
```

## CLI UX Design

### Principles

1. **Immediate Feedback**: Show what's happening
2. **Progressive Disclosure**: Simple by default, powerful when needed
3. **Discoverability**: Help is always available
4. **Consistency**: Same patterns across commands
5. **Safety**: Confirm destructive operations

### Output Formatting

```python
# Success
✓ Model downloaded: qwen3-tts (1.7GB)

# Progress
⠋ Generating speech... 45% complete

# Error
✗ Error: Model 'invalid' not found
  Tip: Search available models with: ttx search tts

# Info
ℹ Using GPU: NVIDIA RTX 3080
```

### Help Text Example

```
ttx generate --help

Usage: ttx generate [OPTIONS] TEXT

  Generate speech from text using a TTS model.

Arguments:
  TEXT  The text to convert to speech (use - to read from stdin)

Options:
  -m, --model TEXT       Model to use [default: qwen3-tts]
  -o, --output PATH      Output file path [default: auto-generated]
  -v, --voice PATH       Reference voice sample for cloning
  --speed FLOAT          Speed multiplier [default: 1.0]
  --help                 Show this message and exit

Examples:
  # Basic generation
  ttx generate "Hello world"
  
  # With specific model
  ttx generate "Hello" --model moss-tts
  
  # With voice cloning
  ttx generate "Hello" --voice reference.wav -o cloned.wav
  
  # From file
  ttx generate - < input.txt --output speech.wav
```

## Deployment & Distribution

### Installation

```bash
# From PyPI (future)
pip install ttx

# From source (development)
git clone https://github.com/user/ttx
cd ttx
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Entry Points

```toml
[project.scripts]
ttx = "ttx.cli:main"
```

### Platform Support

- **Primary**: Linux (Ubuntu 22.04+)
- **Secondary**: macOS (ARM64, x86_64)
- **Future**: Windows (WSL2, native)

## Monitoring & Observability

### Metrics to Track (Future)
- Model download success rate
- Generation success rate
- Average generation time
- Cache hit rate
- Popular models
- Error frequency by type

### Logging Strategy
- Console: User-friendly messages
- File: Detailed debug information
- Structured: JSON format for parsing
- Rotation: Size-based log rotation

## Open Questions & Decisions

### 1. CLI Framework
**Decision**: Typer + Rich
**Rationale**: Modern, great DX, excellent for user-facing CLIs

### 2. Default Model
**Decision**: TBD after testing
**Options**: 
- Qwen3-TTS-1.7B (good quality, reasonable size)
- kani-tts-2-en (smaller, faster)
**Criteria**: Quality, size, speed, language support

### 3. Audio Format
**Decision**: WAV for MVP, add MP3/OGG later
**Rationale**: WAV is universal, no codec dependencies

### 4. GPU Support
**Decision**: Auto-detect and use if available
**Fallback**: CPU with clear warning about speed

### 5. Voice Cloning Approach
**Decision**: TBD pending model research
**Options**:
- Model-specific (Qwen3-CustomVoice)
- Separate encoder model
- Hybrid approach

## Future Architecture Considerations

### Server Mode
Later, support running as a service:
```bash
ttx serve --host 0.0.0.0 --port 8000
```

### Streaming API
Support real-time streaming for long texts:
```python
for chunk in engine.generate_stream(long_text):
    yield chunk
```

### Distributed Generation
For very large batch jobs (far future):
- Support multiple GPU workers
- Queue system (Celery/RQ)
- Progress tracking across workers

## References

### Similar Projects
- **coqui-tts**: Full TTS toolkit (archived)
- **TTS**: Mozilla TTS (legacy)
- **pyttsx3**: Simple TTS wrapper (offline)
- **gTTS**: Google TTS API wrapper

### Model Documentation
- [HuggingFace TTS Models](https://huggingface.co/models?pipeline_tag=text-to-speech)
- [Transformers TTS Guide](https://huggingface.co/docs/transformers/tasks/text-to-speech)
- [PyTorch Audio](https://pytorch.org/audio/)

### Best Practices
- [Click vs Typer](https://typer.tiangolo.com/alternatives/)
- [Structuring Python Projects](https://docs.python-guide.org/writing/structure/)
- [CLI Guidelines](https://clig.dev/)

---

**Last Updated**: 2026-02-16
**Status**: Planning Phase
**Next Review**: After MVP completion
