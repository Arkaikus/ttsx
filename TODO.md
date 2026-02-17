# TTX Project Roadmap

## Project Overview
A modern CLI tool for managing text-to-speech models and generation, inspired by Python's `uv` package manager design philosophy.

## Phase 0: Infrastructure Improvements 🎯 HIGH PRIORITY

### 0.1 Async/Await Support ✅ DONE
**Priority**: HIGH  
**Status**: ✅ Completed

Asyncio support for concurrent operations and better UX.

**What was implemented**:
- [x] Async model size fetching with `get_model_size_async()`
- [x] Concurrent size fetching in search command
- [x] Live table updates with Rich Live display
- [x] Removed `--fetch-sizes` flag - always fetch concurrently
- [x] Background operations with progress indicators

**Key Features**:
- Fetches 5+ model sizes concurrently in ~4 seconds
- Shows "Loading..." initially, updates as sizes arrive
- Better user experience with progressive loading
- No blocking operations in CLI commands

**Implementation Details**:
```python
# Async helper in types.py
async def get_model_size_async(model: ModelInfo) -> Optional[int]:
    """Non-blocking size fetch using thread pool executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: get_model_size(model, fetch_accurate=True)
    )

# Usage in search command
async def search_command_async(query: str, limit: int):
    models = list(hub.search_models(query, limit))
    
    # Fetch sizes concurrently
    fetch_tasks = [fetch_and_update_size(i, m) for i, m in enumerate(models)]
    
    # Update table as each completes
    with Live(table) as live:
        for coro in asyncio.as_completed(fetch_tasks):
            index, size = await coro
            # Update table row...
```

**Next Steps for Async**:
- [ ] Async model downloads (parallel chunk fetching)
- [ ] Async cache operations
- [ ] Async generation pipeline (future)

---

## Phase 1: MVP Core (Foundation)

### 1.1 Project Setup
- [x] Initialize project with uv
- [x] Configure pyproject.toml for Python 3.12+ (tested with 3.14)
- [x] Set up development dependencies (pytest, ruff, mypy)
- [x] Create basic CLI structure with Typer + Rich
- [x] Set up logging infrastructure
- [x] Configure project structure (src layout)

### 1.2 Model Management
- [x] Implement model search from HuggingFace Hub
  - [x] Filter by pipeline_tag=text-to-speech
  - [x] Filter by library=pytorch
  - [x] Display model metadata (size, downloads, likes, modified date)
- [x] Implement model download/caching
  - [x] Use HuggingFace Hub API
  - [x] Local cache management (~/.ttx/models/)
  - [x] Model registry with JSON persistence
- [x] List installed models command
- [x] Remove/clean models command
- [x] Cache management with LRU eviction
- [ ] Model update/upgrade functionality (Future)

### 1.3 Basic TTS Generation ⚠️ IN PROGRESS
- [ ] Implement text-to-speech generation
  - [ ] Support for popular models (Qwen3-TTS, MOSS-TTS, etc.)
  - [ ] WAV file output
  - [ ] Configurable sample rate and audio parameters
- [ ] Text input methods
  - [ ] Direct text string input
  - [ ] Text file input
  - [ ] Stdin support for piping
- [ ] Output options
  - [ ] Specify output file path
  - [ ] Auto-naming with timestamps
  - [ ] Directory output for batch processing

**Note**: Model management infrastructure is complete. Generation engine is next.

### 1.4 CLI Commands (MVP)
```bash
ttx search [query]              # ✅ Search/list models on HF (with size info)
ttx install <model-name>        # ✅ Download and cache model
ttx models                      # ✅ Show installed models (with cache stats)
ttx generate "text" -m model    # ⏳ Generate speech from text (TODO)
ttx remove <model-name>         # ✅ Remove cached model
ttx info <model-name>           # ✅ Show model details (with size)
ttx hw                          # ✅ Show hardware info (single unified table)
ttx version                     # ✅ Show ttx version
```

**Implemented (7/8 commands)**:
- ✅ CLI refactored into `commands/` folder for scalability
- ✅ All models use Pydantic for validation
- ✅ Beautiful Rich tables with size information
- ✅ Hardware detection with single unified table
- ⏳ TTS generation command pending

### 1.5 Hardware Detection ✅ COMPLETE
- [x] Implement hardware information command
  - [x] Detect CUDA availability and version
  - [x] Show GPU model and count
  - [x] Display total and available VRAM
  - [x] Show CPU info (cores, model)
  - [x] Display system RAM
  - [x] Detect MPS (Apple Silicon) support
  - [x] Show PyTorch version and build info
  - [x] Recommend suitable models based on hardware
  - [x] Single unified table (improved UX)
  - [x] JSON output option for scripting

### 1.6 Hardware-Based Model Filtering ✅ COMPLETED
**Goal**: Prevent users from downloading models that won't fit in VRAM

#### Phase 1: Core Infrastructure ✅ DONE
- [x] Create `HardwareRequirements` class (`src/ttx/hardware_requirements.py`)
  - [x] `estimate_vram()` - Calculate VRAM with overhead
    - FP32: 1.5x multiplier (full precision)
    - FP16: 1.2x multiplier (recommended)
    - INT8: 1.15x multiplier (quantized)
    - INT4: 1.1x multiplier (heavily quantized)
  - [x] `check_compatibility()` - Check model compatibility
  - [x] `detect_precision()` - Detect quantization from model ID/tags
- [x] Add `CompatibilityStatus` enum (`hardware_requirements.py`)
  - [x] FITS (green): Model fits comfortably
  - [x] TIGHT (yellow): < 20% VRAM headroom
  - [x] TOO_LARGE (red): Won't fit in VRAM
  - [x] CPU_ONLY (cyan): No GPU available
  - [x] UNKNOWN (gray): Can't determine
- [x] Add `Precision` enum for quantization levels
  - [x] FP32, FP16, BF16, INT8, INT4, UNKNOWN

#### Phase 2: UI Integration ✅ DONE
- [x] Update search command (`commands/search.py`)
  - [x] Add "HW" column to table with compatibility indicators
  - [x] Show user's hardware in header (GPU model + VRAM)
  - [x] Add legend (✓/⚠/✗/ℹ/? meanings)
  - [x] Add `--compatible` flag (show only compatible models)
  - [x] Async compatibility checking with live updates
- [x] Update info command (`commands/models.py`)
  - [x] Add "Hardware Compatibility" panel
  - [x] Show estimated VRAM usage with precision
  - [x] Display exact amount model exceeds VRAM
  - [x] Suggest quantized alternatives automatically
- [ ] Update install command (`commands/models.py`)  # Future
  - [ ] Pre-install hardware check
  - [ ] Confirmation prompt if incompatible
  - [ ] Options: 1) Install anyway 2) Find quantized 3) Choose smaller 4) Cancel

#### Phase 3: Quantization Detection ✅ DONE
- [x] Implement quantized model pattern matching
  - [x] Detect GPTQ models (`-gptq`, `-4bit`)
  - [x] Detect GGUF models (`-gguf`, `-Q4`, `-Q8`)
  - [x] Detect AWQ models (`-awq`)
  - [x] Detect INT8/INT4 models (`int8`, `int4`, `8bit`, `4bit`)
  - [x] Detect FP16/BF16 variants
- [x] `find_quantized_versions()` function
  - [x] Pattern-based suggestions for quantized variants
  - [x] Suggests INT8, INT4, FP16 versions
  - [x] Shows top 3 suggestions
- [x] Auto-suggest during info if model too large

#### Phase 4: Configuration (0.5 days)
- [ ] Add hardware filtering settings to `config.py`
  - [ ] `show_hardware_warnings` (default: true)
  - [ ] `auto_suggest_quantized` (default: true)
  - [ ] `default_precision` (default: "fp16")
  - [ ] `vram_safety_margin` (default: 0.2 = 20%)
- [ ] Support config file (`~/.ttx/config.toml`)
- [ ] Support environment variables (`TTX_*`)

#### Design Decisions
**Warn vs Block**: Warn but allow installation (users know best)
**Default Behavior**: Show compatibility by default (transparency)
**Thresholds**: 70% (fits), 95% (tight), >95% (too large)
**CPU-only**: Show all models with "slower on CPU" note
**MPS**: Use RAM instead of VRAM for unified memory

#### Success Metrics
- [ ] Track OOM errors before/after feature
- [ ] % of users who choose quantized alternatives
- [ ] User satisfaction survey
- [ ] Reduction in "model won't run" support requests

## Phase 2: Advanced Features

### 2.1 Voice Cloning (Zero-Shot)
- [ ] Research and integrate zero-shot TTS models
  - [ ] Evaluate models supporting voice cloning (VALL-E style)
  - [ ] Test with Qwen3-TTS-CustomVoice, SoulX-Singer
- [ ] Voice sample processing
  - [ ] Accept WAV/MP3 reference audio
  - [ ] Voice embedding extraction
  - [ ] Voice profile caching
- [ ] Cloning command interface
```bash
ttx clone --voice reference.wav --text "text" -o output.wav
ttx voices list                 # Show cached voice profiles
ttx voices add name ref.wav     # Save voice profile
```

### 2.2 Batch Processing
- [ ] Batch text file processing
- [ ] CSV/JSON input support with multiple speakers
- [ ] Parallel generation for speed
- [ ] Progress bars and status reporting
- [ ] Resume interrupted batch jobs

### 2.3 Voice Customization
- [ ] Pitch adjustment
- [ ] Speed control
- [ ] Volume normalization
- [ ] Emotion/style control (if model supports)
- [ ] Language/accent selection

### 2.4 Quality of Life Features
- [ ] Interactive REPL mode for quick testing
- [ ] Configuration file support (~/.ttx/config.toml)
- [ ] Model presets/profiles
- [ ] Output format options (WAV, MP3, OGG)
- [ ] Preview/play audio after generation (optional)

## Phase 3: Optimization & Polish

### 3.1 Performance
- [ ] GPU acceleration support
- [ ] Model quantization options (FP16, INT8)
- [ ] Streaming generation for long texts
- [ ] Memory optimization for large models
- [ ] Caching strategy for repeated generations

### 3.2 Developer Experience
- [ ] Comprehensive error messages
- [ ] Detailed logging with verbosity levels
- [ ] Dry-run mode for testing
- [ ] Shell completion (bash, zsh, fish)
- [ ] Man pages / comprehensive help

### 3.3 Documentation
- [ ] User guide with examples
- [ ] API documentation for library usage
- [ ] Video tutorials
- [ ] Troubleshooting guide
- [ ] Performance tuning guide

### 3.4 Testing & Quality
- [ ] Unit tests for all modules
- [ ] Integration tests with real models
- [ ] CI/CD pipeline setup
- [ ] Performance benchmarks
- [ ] Security audit (model source verification)

## Phase 4: Ecosystem & Extensions

### 4.1 Library Mode
- [ ] Python API for programmatic usage
- [ ] Async/await support
- [ ] Batch API
- [ ] Streaming API

### 4.2 Advanced Model Management
- [ ] Model search filters (language, size, quality)
- [ ] Model benchmarking tools
- [ ] Model comparison utilities
- [ ] Custom model registry support
- [ ] Model quantization tools

### 4.3 Integrations
- [ ] REST API server mode
- [ ] WebSocket support for real-time streaming
- [ ] Docker container
- [ ] Plugin system for custom processors
- [ ] Integration with common audio tools

### 4.4 Community Features
- [ ] Share voice profiles (privacy-aware)
- [ ] Model recommendations based on use case
- [ ] Community model registry
- [ ] Usage statistics and telemetry (opt-in)

## Technical Debt & Maintenance

- [ ] Dependency updates strategy
- [ ] Backwards compatibility policy
- [ ] Migration guides for major versions
- [ ] Performance regression testing
- [ ] Security vulnerability scanning

## Nice-to-Have Features

- [ ] Multi-language UI support
- [ ] Web UI for non-technical users
- [ ] Audio effects pipeline (reverb, eq, compression)
- [ ] SSML (Speech Synthesis Markup Language) support
- [ ] Phoneme-level control for advanced users
- [ ] Real-time synthesis mode for live applications
- [ ] Text preprocessing (number expansion, abbreviations)
- [ ] Prosody control (emphasis, pauses, intonation)

## Success Metrics

- [ ] Installation time < 30 seconds
- [ ] First generation < 2 minutes (including model download)
- [ ] Support top 10 popular TTS models from HuggingFace
- [ ] CLI response time < 100ms for non-generation commands
- [ ] Clear documentation with 90%+ coverage
- [ ] Community adoption: 100+ GitHub stars in first 3 months

## Current Priority: Phase 1 (MVP Core)

Focus on getting a working, reliable CLI that can:
1. Search and download TTS models from HuggingFace
2. Generate speech from text with at least 2-3 popular models
3. Manage model cache efficiently
4. Provide excellent CLI UX with clear feedback

**Next Immediate Steps:**
1. Choose CLI framework (Click vs Rich/Typer)
2. Set up project structure (src layout)
3. Implement HuggingFace Hub integration
4. Create basic model downloader
5. Implement first TTS model integration (start with Qwen3-TTS or simpler model)
