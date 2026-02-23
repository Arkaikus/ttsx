# TTSX - Agent/LLM Development Guide

## Project Overview

**ttsx** is a modern command-line interface (CLI) tool for text-to-speech (TTS) generation and model management. Think of it as "`uv` for TTS models" - fast, reliable, and user-friendly.

### Core Objectives
1. **Model Management**: Search, download, cache, and manage TTS models from HuggingFace Hub
2. **Speech Generation**: Convert text to natural-sounding speech using SOTA models
3. **Voice Cloning**: Zero-shot voice cloning using reference audio samples
4. **Developer Experience**: Intuitive CLI with excellent error messages and documentation

## Tech Stack

### Core Technologies
- **Python**: 3.14+ (using latest features)
- **Package Manager**: uv (for fast dependency management)
- **CLI Framework**: Click or Typer/Rich (TBD - see decision below)
- **Model Source**: HuggingFace Hub (PyTorch models)
- **Audio Processing**: torchaudio, soundfile, librosa
- **Model Framework**: PyTorch, transformers

### Key Libraries
```toml
[dependencies]
torch = ">=2.5.0"
torchaudio = ">=2.5.0"
transformers = ">=4.50.0"
huggingface-hub = ">=0.27.0"
typer = ">=0.15.0"  # CLI framework
rich = ">=13.9.0"  # Terminal output
soundfile = ">=0.13.0"
pydantic = ">=2.10.0"  # Configuration & validation
pydantic-settings = ">=2.6.0"
psutil = ">=6.1.0"  # System info
py-cpuinfo = ">=9.0.0"  # CPU details
```

### Development Dependencies
```toml
[tool.uv.dev-dependencies]
pytest = ">=8.3.0"
pytest-cov = ">=6.0.0"
ruff = ">=0.8.0"  # Linting & formatting
mypy = ">=1.13.0"  # Type checking
pytest-mock = ">=3.14.0"
```

## Project Structure

```
ttsx/
├── src/
│   └── ttsx/
│       ├── __init__.py
│       ├── __main__.py          # Entry point for `python -m ttsx`
│       ├── cli.py                # Main CLI commands
│       ├── config.py             # Configuration management
│       ├── cache.py              # Local model cache management
│       ├── hardware.py           # Hardware detection and info
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── hub.py            # HuggingFace Hub API integration
│       │   ├── loader.py         # Model loading and initialization
│       │   ├── registry.py       # Installed models tracking
│       │   └── types.py          # Model metadata types
│       │
│       ├── generation/
│       │   ├── __init__.py
│       │   ├── engine.py         # Core TTS generation
│       │   ├── processors.py    # Text preprocessing
│       │   └── audio.py          # Audio post-processing
│       │
│       ├── voice/
│       │   ├── __init__.py
│       │   ├── cloner.py         # Voice cloning logic
│       │   ├── encoder.py        # Voice embedding extraction
│       │   └── profiles.py       # Voice profile management
│       │
│       └── utils/
│           ├── __init__.py
│           ├── logger.py         # Logging setup
│           ├── progress.py       # Progress reporting
│           ├── validators.py     # Input validation
│           └── exceptions.py     # Custom exceptions
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── docs/
│   ├── getting-started.md
│   ├── commands.md
│   └── examples/
│
├── TODO.md                       # This roadmap
├── AGENTS.md                     # This file
├── ARCHITECTURE.md               # Architecture decisions
├── pyproject.toml
├── uv.lock
├── README.md
└── .gitignore
```

## Code Conventions

### Style Guidelines
- **Formatter**: Ruff (configured to replace Black)
- **Linter**: Ruff (replaces flake8, isort, etc.)
- **Type Hints**: Mandatory for all public functions
- **Docstrings**: Google-style docstrings
- **Line Length**: 100 characters max

### Naming Conventions
- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/Variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: `_leading_underscore`

### Data Modeling Strategy 🔴 IMPORTANT

**Use upstream types when available**, don't duplicate them. Create Pydantic models only for our own domain-specific data.

**Current Approach**:
- ✅ **ModelInfo**: Use `huggingface_hub.hf_api.ModelInfo` directly (upstream dataclass)
- ✅ **InstalledModel**: Our own Pydantic model for local tracking
- ✅ **Helper Functions**: Add utility functions like `get_model_size()`, `format_model_size()`

**Rationale**:
- Avoids duplication and stays in sync with upstream changes
- HuggingFace's ModelInfo already has all fields we need (id, author, downloads, siblings, etc.)
- We only add our own models for domain-specific data not in upstream

### Pydantic Usage (for our own models)

**When creating NEW domain models, use Pydantic**. This ensures:
- Automatic validation
- JSON serialization/deserialization
- Type coercion and conversion
- Consistent API across the codebase

**Where to use what**:
- ✅ **Upstream types**: Use `huggingface_hub.hf_api.ModelInfo` for HF models
- ✅ **Pydantic models**: Configuration (`TTSXConfig`), local data (`InstalledModel`)
- ✅ **Helper functions**: Add utilities like `get_model_size()` for upstream types
- ❌ **Don't duplicate**: Never recreate types that exist in dependencies

**Model Size Fetching**:

HuggingFace's `ModelInfo.siblings[].size` is often `None`, so we use `get_paths_info()` to query actual file sizes:

```python
from huggingface_hub import HfApi, get_paths_info

def get_model_size(model: ModelInfo, fetch_accurate: bool = True) -> Optional[int]:
    """Get accurate model size by querying file sizes.
    
    Steps:
    1. Try siblings first (fast but often None)
    2. If fetch_accurate=True:
       a. List all repo files
       b. Filter for model weights (.safetensors, .bin, .pt)
       c. Query sizes with get_paths_info()
       d. Sum total
    """
    # Fast path: check siblings
    if model.siblings:
        total = sum(s.size or 0 for s in model.siblings)
        if total > 0:
            return total
    
    # Accurate path: query API
    if fetch_accurate:
        api = HfApi()
        all_files = api.list_repo_files(model.id, repo_type="model")
        weight_files = [f for f in all_files 
                       if f.endswith(('.safetensors', '.bin', '.pt', '.pth'))]
        
        if weight_files:
            paths_info = list(get_paths_info(model.id, weight_files, repo_type="model"))
            return sum(info.size for info in paths_info if info.size)
    
    return None
```

**Async Implementation** 🔴 NEW:

All I/O operations should be async for better performance and UX:

```python
import asyncio
from typing import List
from rich.live import Live
from rich.table import Table

async def get_model_size_async(model: ModelInfo) -> int:
    """Async version - fetch size without blocking.
    
    Uses asyncio to fetch sizes concurrently.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: get_model_size(model, fetch_accurate=True))

async def search_with_live_updates(query: str, limit: int):
    """Search and show live-updating table.
    
    Pattern:
    1. Fetch models list (fast)
    2. Show table with "Loading..." for sizes
    3. Fetch sizes concurrently in background
    4. Update table rows as sizes arrive
    """
    # Get models fast
    hub = HuggingFaceHub()
    models = await hub.search_models_async(query, limit)
    
    # Create table with loading indicators
    table = Table(title="Found TTS Models")
    table.add_column("Model ID")
    table.add_column("Size")
    table.add_column("Downloads")
    
    # Add rows with loading state
    for model in models:
        table.add_row(model.id, "[dim]Loading...[/dim]", f"{model.downloads:,}")
    
    # Show table and update live
    with Live(table, refresh_per_second=4) as live:
        # Fetch sizes concurrently
        tasks = [get_model_size_async(m) for m in models]
        
        # Update as each completes
        for i, size in enumerate(asyncio.as_completed(tasks)):
            size_bytes = await size
            # Update table row i with actual size
            table.columns[1].cells[i] = format_model_size(size_bytes)
            live.update(table)
```

**Why Async**:
- ✅ Fetch 20 model sizes concurrently (faster overall)
- ✅ Show immediate results with loading indicators
- ✅ Better perceived performance (progressive loading)
- ✅ No `--fetch-sizes` flag needed - always fetch
- ✅ Non-blocking operations throughout

**Example (using upstream type + async)**:
```python
import asyncio
from huggingface_hub.hf_api import ModelInfo
from huggingface_hub import get_paths_info, HfApi

def get_model_size(model: ModelInfo, fetch_accurate: bool = True) -> Optional[int]:
    """Synchronous size fetching.
    
    Note: siblings.size is often None, so we use get_paths_info 
    to query actual file sizes from the HF API.
    """
    # Try fast path first (siblings)
    if model.siblings:
        total = sum(s.size or 0 for s in model.siblings)
        if total > 0:
            return total
    
    # Fetch accurate sizes from API
    if fetch_accurate:
        api = HfApi()
        files = api.list_repo_files(model.id, repo_type="model")
        model_files = [f for f in files if f.endswith(('.safetensors', '.bin', '.pt'))]
        
        if model_files:
            paths_info = list(get_paths_info(model.id, model_files, repo_type="model"))
            return sum(info.size for info in paths_info if info.size)
    
    return None

async def get_model_size_async(model: ModelInfo) -> Optional[int]:
    """Async version for concurrent fetching."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: get_model_size(model, fetch_accurate=True)
    )
```

**Example (our own Pydantic model)**:
```python
from pydantic import BaseModel, Field, computed_field

class ModelInfo(BaseModel):
    """Model information from HuggingFace."""
    
    model_id: str = Field(..., description="Full model ID")
    downloads: int = Field(default=0, ge=0)
    size_bytes: Optional[int] = Field(None, ge=0)
    
    model_config = {"frozen": False}
    
    @computed_field  # type: ignore[misc]
    @property
    def size_gb(self) -> Optional[float]:
        """Computed property for size in GB."""
        if self.size_bytes:
            return self.size_bytes / (1024**3)
        return None
```

**DON'T use dataclasses** for models that need validation or JSON serialization.

### Type Hints Example
```python
from pathlib import Path
from typing import Optional

def generate_speech(
    text: str,
    model_name: str,
    output_path: Path,
    voice_sample: Optional[Path] = None,
) -> Path:
    """Generate speech from text using specified model.
    
    Args:
        text: The text to convert to speech
        model_name: Name of the TTS model to use
        output_path: Where to save the generated audio
        voice_sample: Optional reference audio for voice cloning
        
    Returns:
        Path to the generated audio file
        
    Raises:
        ModelNotFoundError: If model is not installed
        AudioGenerationError: If generation fails
    """
    ...
```

### Error Handling
- Use custom exceptions for domain-specific errors
- Provide actionable error messages
- Include suggestions for fixing common issues
- Log detailed errors, show user-friendly messages

```python
class TTSXError(Exception):
    """Base exception for ttsx"""
    pass

class ModelNotFoundError(TTSXError):
    """Raised when requested model is not found"""
    def __init__(self, model_name: str):
        self.model_name = model_name
        super().__init__(
            f"Model '{model_name}' not found. "
            f"Install it with: ttsx install {model_name}"
        )
```

## CLI Framework Decision

### ✅ Decision: Typer + Rich

**Rationale**: For a modern CLI in 2026, Typer's automatic type conversion and Rich's beautiful output make development faster and more maintainable. The Pydantic validation aligns well with our data models.

**Key Benefits**:
- Type hints automatically become CLI arguments
- Rich tables, progress bars, and colors out of the box
- Less boilerplate than Click
- Excellent for displaying complex info (like `ttsx hw` output)
- Great async support (future)

**Comparison**:
- **Click**: More mature but more verbose
- **Typer**: Modern, less code, better DX
- **Rich**: Essential for beautiful hardware info tables

## Key Design Patterns

### 1. Repository Pattern
Separate data access (HuggingFace API, local cache) from business logic.

```python
class ModelRepository:
    """Abstract model storage operations"""
    def search(self, query: str) -> list[ModelInfo]: ...
    def download(self, model_id: str) -> Path: ...
    def get_cached(self, model_id: str) -> Optional[Path]: ...
```

### 2. Strategy Pattern
Different TTS models have different APIs. Use strategy pattern for model-specific implementations.

```python
class TTSStrategy(Protocol):
    """Interface for TTS model implementations"""
    def load_model(self, model_path: Path) -> Any: ...
    def generate(self, text: str, **kwargs) -> np.ndarray: ...

class Qwen3TTSStrategy: ...
class MOSSTTSStrategy: ...
```

### 3. Builder Pattern
For complex generation configurations.

```python
class SpeechGenerator:
    def __init__(self):
        self._text: Optional[str] = None
        self._model: Optional[str] = None
        # ...
    
    def with_text(self, text: str) -> "SpeechGenerator": ...
    def with_model(self, model: str) -> "SpeechGenerator": ...
    def build(self) -> AudioOutput: ...
```

### 4. Cache Management
Implement LRU-style cache with size limits.

```python
class ModelCache:
    """Manage local model storage"""
    - Track model usage timestamps
    - Implement size-based eviction
    - Verify model integrity with checksums
    - Atomic downloads with temp files
```

## Configuration Management

### User Configuration File: `~/.ttsx/config.toml`
```toml
[general]
cache_dir = "~/.ttsx/models"
max_cache_size = "10GB"
default_model = "Qwen/Qwen3-TTS-12Hz-1.7B"

[audio]
sample_rate = 22050
bit_depth = 16
format = "wav"

[generation]
device = "auto"  # auto, cpu, cuda, mps
max_workers = 4  # for batch processing
```

### Environment Variables
- `TTSX_CACHE_DIR`: Override cache directory
- `TTSX_HF_TOKEN`: HuggingFace API token for gated models
- `TTSX_DEVICE`: Force device (cpu/cuda/mps)
- `TTSX_LOG_LEVEL`: Logging verbosity

## Model Support Strategy

### Tier 1: Priority Models (MVP)
Focus on popular, well-documented models:
1. **Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice** (1.7B params, voice cloning)
2. **OpenMOSS-Team/MOSS-TTS** (8B params, high quality)
3. **nineninesix/kani-tts-2-en** (0.4B params, lightweight)

### Tier 2: Extended Support
- mistralai/Voxtral models (ASR + TTS)
- Additional language support
- Specialized voices

### Model Adapter System
Create adapters for each model family to handle API differences:
```python
def get_model_adapter(model_id: str) -> TTSStrategy:
    """Factory function to get appropriate model adapter"""
    if "qwen" in model_id.lower():
        return Qwen3Adapter()
    elif "moss" in model_id.lower():
        return MOSSAdapter()
    # ...
```

## Testing Strategy

### Unit Tests
- Test each module in isolation
- Mock external dependencies (HF Hub, file I/O)
- Target 80%+ code coverage

### Integration Tests
- Test with small reference models
- Use fixtures for audio samples
- Test full CLI workflows

### Performance Tests
- Benchmark generation speed
- Memory usage profiling
- Model loading time tests

## Common Patterns for AI Agents

### Adding a New Command
1. Define command in `cli.py` using Typer
2. Add business logic in appropriate module
3. Create custom exceptions if needed
4. Add tests in `tests/unit/`
5. Update documentation

### Adding Model Support
1. Create adapter in `models/` implementing `TTSStrategy`
2. Add model ID patterns to factory function
3. Test with real model or create fixture
4. Document model-specific parameters
5. Add to supported models list in README

### File Organization
- Keep CLI layer thin (only parsing, validation, output formatting)
- Business logic lives in dedicated modules
- Shared utilities in `utils/`
- All paths use `pathlib.Path`, not strings
- Type hints everywhere - let mypy catch bugs

### Logging Best Practices
```python
import logging
logger = logging.getLogger(__name__)

# Info for user-facing messages
logger.info("Downloading model %s", model_id)

# Debug for developer info
logger.debug("Model cache hit: %s", cache_path)

# Warning for recoverable issues
logger.warning("Model not in cache, downloading...")

# Error for failures
logger.error("Failed to load model: %s", error)
```

## Development Workflow

### Setting Up Development Environment
```bash
# Clone and setup
git clone <repo>
cd ttsx
uv venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run linter/formatter
ruff check .
ruff format .

# Type checking
mypy src/
```

### Before Committing
1. Run `ruff format .` to format code
2. Run `ruff check .` to lint
3. Run `mypy src/` for type checking
4. Run `pytest` to ensure tests pass
5. Update documentation if adding features
6. Add entry to CHANGELOG.md (if exists)

## API Design Principles

### CLI Commands Should Be:
- **Intuitive**: Follow Unix conventions (list, install, remove)
- **Consistent**: Same flag names across commands (--model, --output)
- **Composable**: Work well with pipes and other tools
- **Fast**: Show progress for long operations
- **Safe**: Confirm destructive operations

### Example CLI Flow
```bash
# Check hardware capabilities
ttsx hw

# Search for models
ttsx search "qwen tts"
ttsx search "qwen tts" --compatible      # only models that fit VRAM

# Install a model
ttsx install Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice

# Generate speech with a predefined voice
ttsx generate "Hello world" --voice Serena --output hello.wav

# Read from file or stdin
ttsx generate --text-file script.txt --output narration.wav
echo "Hello" | ttsx generate -

# Voice cloning — direct audio file
ttsx clone "Hello world" --audio reference.wav --output cloned.wav
ttsx clone "Hello world" \
    --audio reference.wav \
    --ref-text "Transcript of reference audio" \
    --output cloned.wav

# Voice cloning — saved profiles (reusable)
ttsx voices add narrator reference.wav --ref-text "My reference."
ttsx voices list
ttsx clone "Hello world" --profile narrator --output hello.wav

# List installed models + cache stats
ttsx models

# Model info with hardware compatibility
ttsx info Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice

# Remove model
ttsx remove Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
```

## Security Considerations

1. **Model Verification**: Verify checksums when downloading
2. **Sandboxing**: Run model inference in controlled environment
3. **Input Validation**: Sanitize text input (prevent injection)
4. **Token Management**: Secure HF token storage
5. **Privacy**: Never send user data without consent

## Performance Guidelines

1. **Lazy Loading**: Only load models when needed
2. **Caching**: Cache model metadata, voice embeddings
3. **Batching**: Process multiple texts efficiently
4. **GPU Utilization**: Automatically use GPU when available
5. **Memory Management**: Clear GPU memory after generation

## User Experience Priorities

1. **Clear Feedback**: Always show what's happening
2. **Progress Indication**: Use progress bars for long operations
3. **Helpful Errors**: Suggest solutions, not just problems
4. **Sensible Defaults**: Work out of the box
5. **Documentation**: Examples for every command

## Hardware Requirements and Compatibility

### VRAM Estimation Guidelines

When implementing hardware compatibility features, use these guidelines:

**Overhead Multipliers** (conservative estimates):
- **FP32** (32-bit floats): 1.5x model size
- **FP16** (16-bit floats): 1.2x model size ← Recommended default
- **INT8** (8-bit quantized): 1.1x model size

**Rationale**: Models need extra VRAM for:
- Activation tensors during forward pass
- KV cache for attention mechanisms
- Temporary buffers and intermediate results
- Framework/driver overhead
- Safety margin (20%)

**Compatibility Thresholds**:
- **Green (FITS)**: Model uses < 70% of available VRAM
- **Yellow (TIGHT)**: Model uses 70-95% of VRAM
- **Red (TOO_LARGE)**: Model uses > 95% of VRAM

**Example**:
```python
# 3.4 GB model with FP16 precision
model_size = 3.4 * 1024**3  # bytes
overhead = 1.2
safety = 1.2
required = (model_size / 1024**3) * overhead * safety
# = 3.4 * 1.2 * 1.2 = 4.9 GB needed

# User has 4 GB VRAM available
usage = 4.9 / 4.0 = 1.225 (122.5%)
# Status: TOO_LARGE (red)
```

### Quantization Patterns

When searching for quantized versions, look for these patterns:

```python
QUANTIZATION_PATTERNS = {
    "gptq": ["-gptq", "-GPTQ", "-4bit", "-8bit"],
    "gguf": ["-gguf", "-GGUF", "-Q4", "-Q8", ".gguf"],
    "awq": ["-awq", "-AWQ"],
    "native": ["-int8", "-int4", "-INT8", "-INT4"],
}
```

**Model Naming Examples**:
- `Qwen3-TTS-1.7B` → `Qwen3-TTS-1.7B-GPTQ`
- `MOSS-TTS` → `MOSS-TTS-int8`
- `model-7B` → `model-7B-GGUF-Q4`

### Hardware-Aware Command Design

When implementing commands that interact with models:

1. **Always check hardware first** if model size is known
2. **Warn, don't block** - let users make final decision
3. **Suggest alternatives** when model won't fit
4. **Show calculations** in verbose mode

**Example Flow**:
```python
def install_command(model_id: str) -> None:
    # 1. Get model info (includes size)
    model_info = hub.get_model_info(model_id)
    
    # 2. Check hardware compatibility
    if model_info.compatibility == CompatibilityStatus.TOO_LARGE:
        # 3. Warn user
        console.print(f"⚠ Model requires {required} GB, you have {available} GB")
        
        # 4. Suggest alternatives
        quantized = find_quantized_versions(model_id)
        if quantized:
            console.print("Found quantized versions:")
            for q in quantized:
                console.print(f"  • {q.model_id} ({q.format_size()})")
        
        # 5. Confirm with user
        if not typer.confirm("Install anyway (will use CPU)?"):
            raise typer.Exit(0)
    
    # Proceed with installation...
```

## Common Tasks for AI Agents

### Task: "Implement hardware compatibility checking"

1. **Create hardware requirements module** (`src/ttsx/hardware_requirements.py`)
   - Implement VRAM estimation with overhead multipliers
   - Add compatibility status calculation
   - Write unit tests for different scenarios

2. **Add compatibility to ModelInfo** (`src/ttsx/models/types.py`)
   - Add `@computed_field` for `compatibility` property
   - Implement `get_hardware_warning()` method
   - Cache hardware detection for performance

3. **Update search command** (`src/ttsx/commands/search.py`)
   - Add compatibility column to results table
   - Show user's hardware at top
   - Add legend explaining status indicators
   - Implement `--compatible` and `--no-hardware-check` flags

4. **Update install command** (`src/ttsx/commands/models.py`)
   - Check compatibility before download
   - Show warning if model won't fit
   - Offer to search for quantized versions
   - Allow user to proceed anyway with confirmation

5. **Test thoroughly**:
   ```python
   # Mock different hardware scenarios
   - 2GB VRAM (entry GPU)
   - 4GB VRAM (common laptop GPU)
   - 8GB VRAM (mid-range GPU)
   - 24GB VRAM (high-end GPU)
   - CPU-only (no GPU)
   ```

### Task: "Add support for a new model"
1. Research model architecture and API
2. Create adapter in `src/ttsx/models/adapters/{model_family}.py`
3. Implement `TTSStrategy` protocol
4. Add model ID pattern to factory in `models/loader.py`
5. Create unit tests with fixtures
6. Add integration test if possible
7. Document in README and model support matrix

### Task: "Add a new CLI command"

**Architecture**: Each command module owns its own `typer.Typer()` app. `cli.py` only wires them via `app.add_typer()`.

**Steps:**

1. Create `src/ttsx/commands/<name>.py` with:
   ```python
   import typer
   app = typer.Typer(help="Short description.")

   # Single-action command (no subcommands):
   @app.callback(invoke_without_command=True)
   def my_command(
       arg: str = typer.Argument(...),
       flag: bool = typer.Option(False, "--flag"),
   ) -> None:
       """Docstring becomes --help text. Include Examples: block."""
       ...

   # OR grouped command (multiple subcommands):
   @app.command("sub")
   def sub_command(...) -> None: ...
   ```

2. Export from `commands/__init__.py`:
   ```python
   from ttsx.commands.<name> import app as <name>_app
   ```

3. Wire in `cli.py` (one line):
   ```python
   app.add_typer(<name>_app, name="<name>")
   ```

4. Write tests, update docs — `cli.py` itself never needs editing for logic changes

### Task: "Improve error handling"
1. Identify error-prone operations
2. Create specific exception classes
3. Add try-except blocks with context
4. Provide helpful error messages
5. Log detailed error for debugging
6. Test error scenarios

### Task: "Optimize performance"
1. Profile with cProfile or py-spy
2. Identify bottlenecks
3. Consider: caching, parallelization, lazy loading
4. Benchmark before/after
5. Document performance characteristics

## Important Notes for AI Agents

### What to AVOID
- ❌ Don't create shell scripts - use pure Python
- ❌ Don't add unnecessary dependencies
- ❌ Don't use `os.path` - use `pathlib.Path`
- ❌ Don't print directly - use logging or Rich console
- ❌ Don't hardcode paths - use configuration
- ❌ Don't ignore type hints - mypy should pass
- ❌ Don't create temporary files without cleanup
- ❌ Don't add comments full of dashes, i.e `# --- section -----------....`

### What to PREFER
- ✅ Use type hints everywhere
- ✅ Use `pathlib.Path` for all file operations
- ✅ Use context managers (`with` statements)
- ✅ Use `rich` for pretty terminal output
- ✅ Use `tqdm` or Rich progress for long operations
- ✅ Use `pydantic` for validation
- ✅ Write docstrings for all public functions
- ✅ Create custom exceptions for domain errors
- ✅ Use dependency injection for testability
- ✅ Follow the existing code style exactly
- ✅ Prefer the use of built-int types instead of the `typing` library

## Testing Guidelines

### Test File Organization
```python
# tests/unit/test_models_hub.py
import pytest
from ttsx.models.hub import search_models

def test_search_models_returns_results():
    """Test that search returns model list"""
    results = search_models("qwen tts")
    assert len(results) > 0
    assert all(hasattr(r, "id") for r in results)

@pytest.mark.parametrize("query", ["", "   ", None])
def test_search_models_invalid_input(query):
    """Test error handling for invalid search queries"""
    with pytest.raises(ValueError):
        search_models(query)
```

### Fixtures
Keep reusable test data in `tests/fixtures/`:
- Small audio samples for voice cloning tests
- Mock model metadata
- Example configuration files

## Documentation Standards

### README.md Should Include
1. Quick start guide (5 commands to get started)
2. Installation instructions
3. Basic usage examples
4. Link to full documentation
5. Contributing guidelines
6. License

### Code Documentation
- Every public function needs a docstring
- Include type hints in addition to docstring
- Provide usage examples in docstrings
- Document exceptions that can be raised

### User Documentation
- Command reference with all options
- Cookbook with common recipes
- Troubleshooting guide
- FAQ section

## Git Workflow

### Branch Strategy
- `main`: Stable, production-ready code
- `develop`: Integration branch for features
- `feature/*`: New features
- `fix/*`: Bug fixes

### Commit Messages
Follow conventional commits:
```
feat: add voice cloning support
fix: resolve memory leak in model loading
docs: update installation instructions
test: add tests for audio processing
refactor: simplify cache management logic
perf: optimize batch processing
```

## Release Strategy

### Versioning (Semantic Versioning)
- `MAJOR.MINOR.PATCH`
- Breaking changes → MAJOR
- New features → MINOR
- Bug fixes → PATCH

### Release Checklist
- [ ] All tests pass
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped in pyproject.toml
- [ ] Git tag created
- [ ] PyPI release (when ready)

## Resources

### Documentation
- [HuggingFace Hub API](https://huggingface.co/docs/huggingface_hub)
- [PyTorch Audio](https://pytorch.org/audio/stable/index.html)
- [Typer Documentation](https://typer.tiangolo.com/)
- [Rich Documentation](https://rich.readthedocs.io/)

### Model Research
- [HuggingFace TTS Models](https://huggingface.co/models?pipeline_tag=text-to-speech&library=pytorch)
- [Papers with Code - TTS](https://paperswithcode.com/task/text-to-speech-synthesis)

### Inspiration Projects
- `uv` - Fast Python package manager
- `rye` - Python project management
- `huggingface-cli` - HF CLI tool
- `coqui-tts` - TTS toolkit

## Questions to Ask

When implementing features, consider:
1. **User Impact**: How does this improve the user experience?
2. **Performance**: Will this slow down the CLI?
3. **Complexity**: Is this the simplest solution?
4. **Testability**: Can we easily test this?
5. **Compatibility**: Does this work on Linux/Mac/Windows?
6. **Dependencies**: Do we need another library for this?

## Current Development Focus

We are in **Phase 2: Advanced Features**. Phase 1 MVP and Phase 2.1 Voice Cloning are complete.

### ✅ Completed

1. ✅ Project structure and CLI framework (Typer + Rich)
2. ✅ HuggingFace Hub integration (search, install, info, remove)
3. ✅ Model registry and cache management (LRU eviction)
4. ✅ TTS generation engine (Qwen3-TTS: CustomVoice, VoiceDesign, Base; MLX)
5. ✅ Hardware detection + VRAM compatibility checking
6. ✅ Async size fetching with live-updating search tables
7. ✅ **Voice cloning system** (Phase 2.1):
   - `src/ttsx/voice/profiles.py` — `VoiceProfile` + `VoiceProfileManager`
   - `src/ttsx/voice/encoder.py` — audio validation + quality checks
   - `src/ttsx/voice/cloner.py` — cloning orchestration
   - `src/ttsx/commands/voices.py` — voices subcommands + clone command
   - `ttsx voices list/add/remove/info` + `ttsx clone`

### 🔄 Next priorities

1. **Phase 2.2** — Batch processing (CSV/JSON input, parallel generation)
2. **Phase 2.3** — Voice customization (pitch, speed, style)
3. **Phase 3.4** — Unit and integration tests for voice cloning
4. **Phase 1.6 Phase 4** — Hardware check on `ttsx install`
5. **Phase 4.1** — Python library API

### Key voice cloning files for agents

| File | Purpose |
|---|---|
| `src/ttsx/voice/profiles.py` | `VoiceProfile` Pydantic model + `VoiceProfileManager` CRUD |
| `src/ttsx/voice/encoder.py` | Audio format validation, duration/quality checks |
| `src/ttsx/voice/cloner.py` | `clone_with_profile()` and `clone_with_audio()` |
| `src/ttsx/commands/voices.py` | `app` — `@app.command("list/add/remove/info")` subcommands |
| `src/ttsx/commands/clone.py` | `app` — `@app.callback` single-action clone command |
| `src/ttsx/cli.py` | Pure wiring: `app.add_typer(voices_app)`, `app.add_typer(clone_app)` |
| `src/ttsx/generation/engine.py` | `QwenTTSEngine.generate()` accepts `ref_audio`/`ref_text` |

## Support

For questions or discussions:
- Check TODO.md for current roadmap
- Check ARCHITECTURE.md for design decisions
- Check test files for usage examples
- Check docs/ for user-facing documentation
