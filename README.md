# TTX - Modern Text-to-Speech CLI

> A fast, modern CLI tool for managing text-to-speech models and generating natural-sounding speech.

✅ **Status**: MVP Complete - Core model management functional!

## Overview

`ttx` is a command-line interface for text-to-speech generation, inspired by modern Python tools like `uv`. It provides easy access to state-of-the-art TTS models from HuggingFace Hub with a focus on speed, simplicity, and developer experience.

## Features

### ✅ Implemented (MVP)
- 🔍 **Model Discovery**: Search and browse TTS models from HuggingFace
- ⚡ **Async Operations**: Concurrent model size fetching with live-updating tables
- 🎯 **Hardware Filtering**: Real-time VRAM compatibility checking
  - Shows which models fit in your GPU before downloading
  - Automatic quantization detection (FP32/FP16/INT8/INT4)
  - Filter to show only compatible models (`--compatible`)
  - Suggests quantized alternatives for oversized models
- 📦 **Model Management**: Install, list, info, and remove TTS models locally
- 💾 **Cache Management**: Automatic cache management with LRU eviction
- 🖥️ **Hardware Detection**: Check GPU/CPU capabilities
- 🎨 **Beautiful CLI**: Rich terminal output with progress bars and tables

### 🚧 Coming Soon
- 🎤 **Speech Generation**: Convert text to natural speech with various voices
- 🎭 **Voice Cloning**: Zero-shot voice cloning from reference audio
- ⚡ **Batch Processing**: Process multiple texts efficiently
- 🎛️ **Voice Customization**: Fine-tune voice characteristics

## Quick Start

```bash
# Install dependencies with uv
cd ttx
uv sync

# Check your hardware capabilities
uv run ttx hw

# Search for TTS models (sizes + hardware compat load in background)
uv run ttx search "qwen tts" --limit 5

# Show only models compatible with your hardware
uv run ttx search "qwen tts" --compatible

# Get information about a specific model (includes hardware compatibility)
uv run ttx info Qwen/Qwen3-TTS-12Hz-0.6B-Base

# Install a model (downloads ~1-2GB)
uv run ttx install Qwen/Qwen3-TTS-12Hz-0.6B-Base

# List installed models
uv run ttx models

# Remove a model
uv run ttx remove Qwen/Qwen3-TTS-12Hz-0.6B-Base
```

### Future Features (Coming Soon)

```bash
# Generate speech (Not yet implemented)
uv run ttx generate "Hello, world!" --model qwen3-tts

# With voice cloning (Not yet implemented)
uv run ttx generate "Hello!" --voice reference.wav --output cloned.wav
```

## Installation

### From Source

```bash
# Clone repository
git clone <repository-url>
cd ttx

# Install with uv (creates venv and installs all dependencies)
uv sync

# Run CLI
uv run ttx --help

# Install with development dependencies
uv sync --all-extras

# Run tests (when available)
uv run pytest

# Format and lint code
uv run ruff check .
uv run ruff format .
```

### Requirements

- Python 3.12+ (tested with 3.14)
- PyTorch 2.5+
- CUDA 12.1+ (optional, for GPU acceleration)
- ~10-50GB disk space (depending on models installed)

## Documentation

- [TODO.md](TODO.md) - Development roadmap and task tracking
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design and architecture
- [AGENTS.md](AGENTS.md) - Guide for AI agents and LLMs working on this project

## Project Status

🚧 **Alpha** - Core MVP is functional! TTS generation coming next.

### ✅ Completed (MVP)
- Project structure and configuration management
- CLI framework with Typer + Rich  
- Hardware detection (`ttx hw`)
- HuggingFace Hub integration
- Model search, info, install, list, and remove commands
- Model registry and cache management with LRU eviction
- Custom exception hierarchy

### 🚧 In Progress
- TTS generation engine
- Model adapters for specific TTS models
- Audio output and post-processing

### 📋 Planned
- Voice cloning support
- Multiple model adapters (Qwen, MOSS, Kani)
- Batch processing
- Performance optimization
- Tests and CI/CD

See [TODO.md](TODO.md) for detailed roadmap.

## Contributing

Contributions welcome! This project is in early stages.

## License

TBD

## Tech Stack

- Python 3.14
- uv (package management)
- Typer + Rich (CLI framework)
- PyTorch (model runtime)
- HuggingFace Transformers (model library)

---

**Note**: This is an active development project. APIs and commands are subject to change.
