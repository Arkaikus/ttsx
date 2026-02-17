# TTX - Agent/LLM Development Guide

## Project Overview

**ttx** is a modern command-line interface (CLI) tool for text-to-speech (TTS) generation and model management. Think of it as "`uv` for TTS models" - fast, reliable, and user-friendly.

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
ttx/
├── src/
│   └── ttx/
│       ├── __init__.py
│       ├── __main__.py          # Entry point for `python -m ttx`
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

### Pydantic Usage 🔴 IMPORTANT

**All data models MUST use Pydantic**, not dataclasses. This ensures:
- Automatic validation
- JSON serialization/deserialization
- Type coercion and conversion
- Consistent API across the codebase

**Where to use Pydantic**:
- ✅ Configuration (`config.py`) - uses `pydantic-settings`
- ✅ Model metadata (`models/types.py`) - `ModelInfo`, `InstalledModel`
- ✅ API responses and data structures
- ✅ Any data that needs validation or serialization

**Example**:
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
class TTXError(Exception):
    """Base exception for ttx"""
    pass

class ModelNotFoundError(TTXError):
    """Raised when requested model is not found"""
    def __init__(self, model_name: str):
        self.model_name = model_name
        super().__init__(
            f"Model '{model_name}' not found. "
            f"Install it with: ttx install {model_name}"
        )
```

## CLI Framework Decision

### ✅ Decision: Typer + Rich

**Rationale**: For a modern CLI in 2026, Typer's automatic type conversion and Rich's beautiful output make development faster and more maintainable. The Pydantic validation aligns well with our data models.

**Key Benefits**:
- Type hints automatically become CLI arguments
- Rich tables, progress bars, and colors out of the box
- Less boilerplate than Click
- Excellent for displaying complex info (like `ttx hw` output)
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

### User Configuration File: `~/.ttx/config.toml`
```toml
[general]
cache_dir = "~/.ttx/models"
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
- `TTX_CACHE_DIR`: Override cache directory
- `TTX_HF_TOKEN`: HuggingFace API token for gated models
- `TTX_DEVICE`: Force device (cpu/cuda/mps)
- `TTX_LOG_LEVEL`: Logging verbosity

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
cd ttx
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
ttx hw

# Search for models
ttx search "qwen tts"

# Install a model
ttx install Qwen/Qwen3-TTS-12Hz-1.7B

# Generate speech
ttx generate "Hello world" --model qwen3-tts --output hello.wav

# With voice cloning
ttx generate "Hello world" \
    --model qwen3-tts \
    --voice reference.wav \
    --output cloned.wav

# Batch processing
ttx batch script.txt --model qwen3-tts --output-dir ./outputs/

# List models
ttx models ls

# Model info
ttx models info qwen3-tts
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

## Common Tasks for AI Agents

### Task: "Add support for a new model"
1. Research model architecture and API
2. Create adapter in `src/ttx/models/adapters/{model_family}.py`
3. Implement `TTSStrategy` protocol
4. Add model ID pattern to factory in `models/loader.py`
5. Create unit tests with fixtures
6. Add integration test if possible
7. Document in README and model support matrix

### Task: "Add a new CLI command"
1. Add command function in `src/ttx/cli.py`
2. Use Typer decorators with type hints
3. Implement business logic in appropriate module
4. Add validation using Pydantic
5. Write tests for command
6. Add help text and examples
7. Update user documentation

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

## Testing Guidelines

### Test File Organization
```python
# tests/unit/test_models_hub.py
import pytest
from ttx.models.hub import search_models

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

As of now, we're in **Phase 1: MVP Core**. The immediate priorities are:

1. ✅ Project structure setup
2. 🔄 Choose and implement CLI framework (Typer + Rich)
3. 🔄 HuggingFace Hub integration for model search/download
4. 🔄 Model cache management system
5. 🔄 Basic TTS generation with at least one model

Focus on getting something working end-to-end before adding advanced features. The goal is to have a functioning `ttx install MODEL && ttx generate "text"` flow as soon as possible.

## Support

For questions or discussions:
- Check TODO.md for current roadmap
- Check ARCHITECTURE.md for design decisions
- Check test files for usage examples
- Check docs/ for user-facing documentation
