# TTX Project Roadmap

## Project Overview
A modern CLI tool for managing text-to-speech models and generation, inspired by Python's `uv` package manager design philosophy.

## Phase 1: MVP Core (Foundation)

### 1.1 Project Setup
- [x] Initialize project with uv
- [x] Configure pyproject.toml for Python 3.14
- [ ] Set up development dependencies (pytest, ruff, mypy)
- [ ] Create basic CLI structure with Click or Rich
- [ ] Set up logging infrastructure
- [ ] Configure project structure (src layout)

### 1.2 Model Management
- [ ] Implement model search from HuggingFace Hub
  - [ ] Filter by pipeline_tag=text-to-speech
  - [ ] Filter by library=pytorch
  - [ ] Display model metadata (size, language, license)
- [ ] Implement model download/caching
  - [ ] Use HuggingFace Hub API
  - [ ] Local cache management (~/.ttx/models/)
  - [ ] Verify model integrity
- [ ] List installed models command
- [ ] Remove/clean models command
- [ ] Model update/upgrade functionality

### 1.3 Basic TTS Generation
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

### 1.4 CLI Commands (MVP)
```bash
ttx list                        # List available models on HF
ttx install <model-name>        # Download and cache model
ttx models                      # Show installed models
ttx generate "text" -m model    # Generate speech from text
ttx remove <model-name>         # Remove cached model
ttx info <model-name>           # Show model details
ttx hw                          # Show hardware info (GPU, VRAM, CUDA)
```

### 1.5 Hardware Detection
- [ ] Implement hardware information command
  - [ ] Detect CUDA availability and version
  - [ ] Show GPU model and count
  - [ ] Display total and available VRAM
  - [ ] Show CPU info (cores, model)
  - [ ] Display system RAM
  - [ ] Detect MPS (Apple Silicon) support
  - [ ] Show PyTorch version and build info
  - [ ] Recommend suitable models based on hardware
- [ ] Hardware-based model filtering
  - [ ] Mark models that won't fit in VRAM
  - [ ] Suggest quantized versions for limited hardware
  - [ ] Auto-select device (cuda/mps/cpu)

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
