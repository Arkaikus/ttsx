# TTSX Architecture Documentation

## Overview

TTSX is designed as a modular, extensible CLI tool for text-to-speech generation and model management. The architecture follows clean separation of concerns with a focus on maintainability and testability.

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
- ✅ `config.py` - `TTSXConfig` (extends `pydantic-settings.BaseSettings`)
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

### 1. CLI Module (`cli.py` + `commands/`)

**Responsibility**: Command-line interface, argument parsing, user output

#### Design: one app per command module

Each file in `commands/` defines and **owns** its own `typer.Typer()` instance. `cli.py` is a pure wiring file — it only calls `app.add_typer()`. No argument definitions or business logic live in `cli.py`.

```
commands/
├── generate.py   → app  (single action, @app.callback)
├── clone.py      → app  (single action, @app.callback)
├── voices.py     → app  (sub-commands: list / add / remove / info)
├── models.py     → app  (sub-commands: list / install / remove / info)
├── search.py     → app  (single action, @app.callback)
├── hardware.py   → app  (single action, @app.callback)
└── version.py    → app  (single action, @app.callback)
```

`cli.py` wires them in one place:

```python
# cli.py — nothing else goes here
from ttsx.commands import generate_app, clone_app, voices_app, models_app, ...

app = typer.Typer(...)
app.add_typer(hw_app,       name="hw")
app.add_typer(generate_app, name="generate")
app.add_typer(clone_app,    name="clone")
app.add_typer(voices_app,   name="voices")
app.add_typer(models_app,   name="models")
app.add_typer(search_app,   name="search")
app.add_typer(version_app,  name="version")
```

#### Two sub-app patterns

**Pattern A — single-action command** (`generate`, `clone`, `hw`, `search`, `version`):

The module's `app` has exactly one entry point defined as the app's callback. Typer invokes it directly when the command is called.

```python
# commands/generate.py
app = typer.Typer(help="Generate speech from text.")

@app.callback(invoke_without_command=True)
def generate(
    text: Optional[str] = typer.Argument(None),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    ...
) -> None:
    """Generate speech from text."""
    # full implementation here — no wrapper needed
```

**Pattern B — command group** (`models`, `voices`):

The module's `app` has multiple `@app.command("name")` subcommands, plus an optional `@app.callback(invoke_without_command=True)` for the default behavior.

```python
# commands/models.py
app = typer.Typer(help="Manage installed TTS models.")

@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        _list_impl()   # ttsx models → defaults to list

@app.command("install")
def install(model_id: str = typer.Argument(...)) -> None: ...

@app.command("list")
def list_models() -> None: ...

@app.command("remove")
def remove(model_id: str = typer.Argument(...), force: bool = ...) -> None: ...

@app.command("info")
def info(model_id: str = typer.Argument(...)) -> None: ...
```

#### Command surface

| Command | Sub-commands | Notes |
|---|---|---|
| `ttsx hw` | — | JSON + verbose flags |
| `ttsx version` | — | |
| `ttsx search` | — | Async live-updating table |
| `ttsx generate` | — | Predefined voices + inline cloning |
| `ttsx clone` | — | Profile or raw audio |
| `ttsx voices` | `list` `add` `remove` `info` | |
| `ttsx models` | `list` `install` `remove` `info` | Default: list |

**Design Notes**:
- `cli.py` stays under ~30 lines — pure wiring, zero logic
- All Typer `Argument`/`Option` definitions live inside the owning module
- Every module is independently importable and testable
- Adding a new command = create `commands/new.py`, add one `add_typer()` line

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

**Storage**: JSON file at `~/.ttsx/models/registry.json`

```json
{
  "models": [
    {
      "id": "Qwen/Qwen3-TTS-12Hz-1.7B",
      "path": "/home/user/.ttsx/models/qwen3-tts",
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

### 4. Voice Module (`voice/`) ✅ Implemented

**Responsibility**: Voice cloning, audio validation, and voice profile management

#### 4.1 Voice Encoder (`encoder.py`)

Provides audio validation and pre-processing utilities. Does **not** extract neural embeddings — the TTS engine handles that internally via its `ref_audio` parameter.

```python
SUPPORTED_FORMATS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}

def validate_audio(audio_path: Path) -> None:
    """Validate existence and format of audio file."""

def get_audio_info(audio_path: Path) -> dict:
    """Return duration, sample_rate, channels, format."""

def check_cloning_suitability(audio_path: Path) -> list[str]:
    """Advisory quality checks — returns list of warning strings."""
    # Warns if duration < 3s or > 30s
    # Warns if sample rate < 16kHz

def prepare_audio_for_cloning(
    audio_path: Path,
    target_sample_rate: Optional[int] = None,
    normalize: bool = True,
) -> tuple[np.ndarray, int]:
    """Load, convert stereo→mono, resample (librosa), peak-normalize."""
```

#### 4.2 Voice Profiles (`profiles.py`)

Persistent named voice profiles backed by copied audio files.

```python
class VoiceProfile(BaseModel):
    """Saved voice profile. Stored as JSON entry."""
    name: str
    audio_path: Path          # Points into ~/.ttsx/voices/audio/
    ref_text: Optional[str]   # Transcript (recommended for quality)
    description: Optional[str]
    language: Optional[str]
    created_at: datetime

    @property
    def audio_exists(self) -> bool: ...

class VoiceProfileManager:
    """CRUD manager for VoiceProfile objects."""
    
    # Storage layout
    # ~/.ttsx/voices/profiles.json   — profile metadata
    # ~/.ttsx/voices/audio/<name>.*  — copied reference audio

    def add(self, name, audio_file, ref_text, ..., overwrite) -> VoiceProfile:
        """Copy audio to managed dir, persist metadata."""

    def remove(self, name) -> bool:
        """Delete audio file and remove metadata entry."""

    def get(self, name) -> Optional[VoiceProfile]: ...
    def list_profiles(self) -> list[VoiceProfile]: ...
    def exists(self, name) -> bool: ...
```

**Storage layout**:
```
~/.ttsx/voices/
├── profiles.json       — JSON map of name → VoiceProfile metadata
└── audio/
    ├── narrator.wav    — copied reference audio
    └── alice.mp3
```

#### 4.3 Voice Cloner (`cloner.py`)

Thin orchestration layer that connects profiles/audio → model registry → TTS engine.

```python
def clone_with_profile(
    text: str,
    profile_name: str,
    model_id: Optional[str] = None,
    output_path: Optional[Path] = None,
) -> Path:
    """Load saved profile, resolve model, delegate to engine."""

def clone_with_audio(
    text: str,
    audio_path: Path,
    model_id: Optional[str] = None,
    ref_text: Optional[str] = None,
    output_path: Optional[Path] = None,
) -> tuple[Path, list[str]]:
    """Validate audio, run quality checks, delegate to engine.
    Returns (output_path, advisory_warnings)."""
```

**Data flow for voice cloning**:
```
ttsx clone "text" --profile narrator
  → VoiceProfileManager.get("narrator")
  → ModelRegistry.get(model_id)
  → get_tts_engine(model_id)          ← factory
  → engine.generate(..., ref_audio=profile.audio_path, ref_text=...)
  → WAV file output
```

### 5. Configuration Module (`config.py`)

**Responsibility**: Manage user configuration and settings

```python
from pydantic_settings import BaseSettings

class TTSXConfig(BaseSettings):
    """Global configuration"""
    
    cache_dir: Path = Path.home() / ".ttsx" / "models"
    max_cache_size: str = "10GB"
    default_model: str = "qwen3-tts"
    device: str = "auto"
    sample_rate: int = 22050
    audio_format: str = "wav"
    
    class Config:
        env_prefix = "TTSX_"
        env_file = ".env"

# Singleton instance
config = TTSXConfig()
```

**Configuration Sources** (priority order):
1. Command-line arguments
2. Environment variables (`TTSX_*`)
3. User config file (`~/.ttsx/config.toml`)
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
    from ttsx.hardware import HardwareDetector
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
        
        from ttsx.hardware import HardwareDetector
        from ttsx.hardware_requirements import HardwareRequirements
        
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

logger = logging.getLogger("ttsx")
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
class TTSXError(Exception):
    """Base exception"""

class ModelError(TTSXError):
    """Model-related errors"""

class ModelNotFoundError(ModelError):
    """Model doesn't exist"""

class ModelDownloadError(ModelError):
    """Failed to download model"""

class GenerationError(TTSXError):
    """Generation failed"""

class AudioError(TTSXError):
    """Audio processing error"""

class ConfigError(TTSXError):
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
        f"[yellow]Tip:[/yellow] Run [cyan]ttsx install {model_id}[/cyan]"
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
class VoiceProfile(BaseModel):
    """Saved voice profile for cloning."""
    name: str
    audio_path: Path            # Managed copy in ~/.ttsx/voices/audio/
    ref_text: Optional[str]     # Transcript of reference audio
    description: Optional[str]
    language: Optional[str]
    created_at: datetime

    @property
    def audio_exists(self) -> bool:
        return self.audio_path.exists()

    def format_created(self) -> str:
        return self.created_at.strftime("%Y-%m-%d %H:%M")
```

**Design note**: We store the raw audio file, not a neural embedding. The TTS engine (e.g. `QwenTTSEngine`) handles embedding extraction internally at inference time, which avoids model-specific embedding format coupling and ensures compatibility across model updates.

## File System Layout

### User Directories

```
~/.ttsx/
├── config.toml              # User configuration (optional)
├── registry.json            # Installed models database
├── models/                  # Model files (cache_dir)
│   ├── Qwen--Qwen3-TTS-12Hz-0.6B-CustomVoice/
│   │   ├── config.json
│   │   ├── model.safetensors
│   │   └── tokenizer/
│   └── Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice/
└── voices/                  # Voice profiles (Phase 2.1)
    ├── profiles.json        # Profile metadata (JSON map)
    └── audio/               # Managed copies of reference audio
        ├── narrator.wav
        └── alice.mp3
```

### Project Structure

```
ttsx/
├── src/ttsx/
│   ├── __init__.py
│   ├── __main__.py          # Entry point: `python -m ttsx`
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

1. Create `src/ttsx/commands/<name>.py`
2. Define `app = typer.Typer(help="...")` and the command as either:
   - `@app.callback(invoke_without_command=True)` for a single-action command
   - `@app.command("sub")` entries for a grouped command
3. Export the app from `commands/__init__.py`
4. Add one line to `cli.py`: `app.add_typer(<name>_app, name="<name>")`
5. Add tests and update documentation

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
  Tip: Search available models with: ttsx search tts

# Info
ℹ Using GPU: NVIDIA RTX 3080
```

### Help Text Example

```
ttsx generate --help

Usage: ttsx generate [OPTIONS] TEXT

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
  ttsx generate "Hello world"
  
  # With specific model
  ttsx generate "Hello" --model moss-tts
  
  # With voice cloning
  ttsx generate "Hello" --voice reference.wav -o cloned.wav
  
  # From file
  ttsx generate - < input.txt --output speech.wav
```

## Deployment & Distribution

### Installation

```bash
# From PyPI (future)
pip install ttsx

# From source (development)
git clone https://github.com/user/ttsx
cd ttsx
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Entry Points

```toml
[project.scripts]
ttsx = "ttsx.cli:main"
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
**Decision**: Store raw audio, delegate embedding extraction to TTS engine  
**Rationale**:
- Avoids coupling to a specific embedding format
- Qwen3-TTS Base models accept raw `(audio, sr)` directly via `generate_voice_clone()`
- Profiles store audio + optional transcript; engine handles the rest
- Simpler than a separate encoder model; can be upgraded later without breaking profiles

## Future Architecture Considerations

### Server Mode
Later, support running as a service:
```bash
ttsx serve --host 0.0.0.0 --port 8000
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

**Last Updated**: 2026-02-21  
**Status**: Phase 2.1 Complete — Voice Cloning implemented  
**Next Review**: After Phase 2.2 (Batch Processing)
