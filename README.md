# ttsx — Modern Text-to-Speech CLI

> A fast, modern CLI for managing TTS models and generating natural-sounding speech — including zero-shot voice cloning.

✅ **Status**: Phase 2.1 Complete — MVP + Voice Cloning functional!

## Features

| Feature | Status |
|---|---|
| Model search (HuggingFace Hub, live size fetching) | ✅ |
| Hardware VRAM compatibility checking | ✅ |
| Model install / list / remove / info | ✅ |
| Cache management with LRU eviction | ✅ |
| Speech generation (Qwen3-TTS, MLX models) | ✅ |
| Predefined voices (9 built-in speakers) | ✅ |
| **Voice profiles** (save & reuse cloned voices) | ✅ **New** |
| **Zero-shot voice cloning** (`ttsx clone`) | ✅ **New** |
| Batch processing | 🚧 Planned |
| Voice customization (pitch, speed) | 🚧 Planned |

## Quick Start

```bash
# Clone and install
git clone <repository-url>
cd ttsx
uv sync

# Check hardware (GPU/VRAM/RAM)
uv run ttsx hw

# Search for compatible models
uv run ttsx search "qwen tts" --compatible

# Install a model (~2-4 GB download)
uv run ttsx install Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice

# Generate speech with a predefined voice
uv run ttsx generate "Hello world!" --voice Serena --output hello.wav

# Clone a voice from a reference audio file
uv run ttsx clone "Hello, this is my voice." --audio reference.wav --output cloned.wav
```

## Installation

### Requirements

- Python 3.12+ (tested with 3.14)
- PyTorch 2.5+
- CUDA 12.1+ (optional, for GPU acceleration)
- 10–50 GB disk space depending on installed models

### From Source

```bash
git clone <repository-url>
cd ttsx
uv sync               # installs all dependencies into .venv
uv run ttsx --help
```

For development (linters, tests):

```bash
uv sync --all-extras
uv run ruff check .
uv run ruff format .
uv run pytest
```

## Command Reference

### Hardware

```bash
ttsx hw                    # GPU, CPU, RAM, PyTorch info
ttsx hw --json             # Machine-readable JSON output
ttsx hw --verbose          # Detailed diagnostics
```

### Model Management

```bash
# Search HuggingFace Hub (sizes + compatibility load concurrently)
ttsx search                          # browse popular TTS models
ttsx search "qwen"                   # keyword search
ttsx search --compatible             # only models that fit your VRAM
ttsx search --limit 10               # limit results

# Model info
ttsx info Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice

# Install / list / remove
ttsx install Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
ttsx models                          # list installed models + cache stats
ttsx remove Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
ttsx remove Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice --force
```

### Speech Generation

Generate speech using a predefined voice or inline reference audio:

```bash
# Basic
ttsx generate "Hello world!"
ttsx generate "Hello world!" --output hello.wav
ttsx generate "Hello world!" --model Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice

# Predefined voices
ttsx generate "Good morning." --voice Serena
ttsx generate "Good morning." --voice Ryan --output morning.wav

# Read text from file or stdin
ttsx generate --text-file script.txt --output narration.wav
echo "Hello world" | ttsx generate -

# Inline voice cloning (no saved profile needed)
ttsx generate "Hello." --ref-audio reference.wav
ttsx generate "Hello." --ref-audio reference.wav --ref-text "Reference transcript"
```

#### Available predefined voices

| Voice | | Voice | | Voice |
|---|---|---|---|---|
| Aiden | | Dylan | | Eric |
| Ono_anna | | Ryan | | Serena |
| Sohee | | Uncle_fu | | Vivian |

List voices for any installed model:

```bash
ttsx voices list --predefined
ttsx voices list --predefined --model Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
```

### Voice Cloning

Voice cloning lets you synthesize speech that sounds like a specific person using a short reference audio sample (3–30 seconds of clean speech works best).

There are two workflows:

#### 1. Direct cloning (no saved profile)

Provide a reference audio file directly to `ttsx clone`:

```bash
# From an audio file — no transcript
ttsx clone "The meeting starts at nine." --audio reference.wav

# With transcript (strongly recommended — improves clone quality)
ttsx clone "The meeting starts at nine." \
  --audio reference.wav \
  --ref-text "Hi, this is a short sample of my voice for cloning." \
  --output output.wav

# From stdin
echo "Hello world" | ttsx clone - --audio reference.wav

# Specify model explicitly
ttsx clone "Hello." --audio reference.wav --model Qwen/Qwen3-TTS-12Hz-0.6B-Base
```

#### 2. Saved voice profiles (recommended for reuse)

Save a voice once, use it anywhere:

```bash
# Save a voice profile
ttsx voices add narrator reference.wav
ttsx voices add narrator reference.wav \
  --ref-text "Hi, this is a sample of my voice." \
  --language English \
  --description "Deep narrator voice"

# List saved profiles
ttsx voices list

# View profile details
ttsx voices info narrator

# Generate speech with saved profile
ttsx clone "Chapter one. The story begins." --profile narrator
ttsx clone "Chapter one." --profile narrator --output chapter1.wav
ttsx clone --text-file chapter1.txt --profile narrator --output chapter1.wav

# Remove a profile
ttsx voices remove narrator
ttsx voices remove narrator --force     # skip confirmation
```

#### Voice profile options

| Option | Description |
|---|---|
| `--ref-text` | Transcript of the reference audio. Strongly recommended — without it, the model uses x-vector mode (lower quality). |
| `--language` | Language of the voice (informational) |
| `--description` | Human-readable note |
| `--overwrite` | Replace an existing profile with the same name |

#### Tips for best clone quality

- **3–15 seconds** of clean, single-speaker speech works best
- Provide `--ref-text` whenever possible
- Use WAV at 16kHz+ for best results
- Avoid noisy recordings, music, or multiple speakers
- `ttsx voices add` warns you if the audio is too short or has a low sample rate

## Supported Models

### Qwen3-TTS (recommended)

| Model | Size | Type | Notes |
|---|---|---|---|
| `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` | ~1.2 GB | CustomVoice | 9 predefined speakers |
| `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | ~3.4 GB | CustomVoice | Higher quality |
| `Qwen/Qwen3-TTS-12Hz-0.6B-Base` | ~1.2 GB | Base | Voice cloning |
| `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | ~3.4 GB | Base | Voice cloning, higher quality |

### MLX (Apple Silicon only)

Search `mlx-community` for optimized Apple Silicon variants:

```bash
ttsx search "mlx qwen tts"
```

## Configuration

Configuration lives at `~/.ttsx/config.toml` (optional):

```toml
[general]
cache_dir = "~/.ttsx/models"     # where models are stored
max_cache_size_gb = 50           # maximum cache size

[generation]
device = "auto"                  # auto, cpu, cuda, mps
```

Environment variables override config file values:

| Variable | Description |
|---|---|
| `TTSX_CACHE_DIR` | Override model cache directory |
| `TTSX_HF_TOKEN` | HuggingFace API token (for gated models) |
| `TTSX_DEVICE` | Force device: `cpu`, `cuda`, `mps` |
| `TTSX_LOG_LEVEL` | Logging verbosity: `DEBUG`, `INFO`, `WARNING` |

## Data Directories

```
~/.ttsx/
├── registry.json            # Installed models index
├── models/                  # Downloaded model weights
└── voices/                  # Voice profiles (Phase 2.1)
    ├── profiles.json        # Profile metadata
    └── audio/               # Managed copies of reference audio
        ├── narrator.wav
        └── alice.mp3
```

## Documentation

- [TODO.md](TODO.md) — Development roadmap and task tracking
- [ARCHITECTURE.md](ARCHITECTURE.md) — System design and implementation details
- [AGENTS.md](AGENTS.md) — Guide for AI agents working on this project

## Project Status

| Phase | Status |
|---|---|
| Phase 0 — Async/concurrent operations | ✅ Complete |
| Phase 1 — MVP (search, install, generate, hardware) | ✅ Complete |
| Phase 2.1 — Voice cloning + profiles | ✅ Complete |
| Phase 2.2 — Batch processing | 🚧 Planned |
| Phase 2.3 — Voice customization | 🚧 Planned |
| Phase 3 — Optimization & polish | 🚧 Planned |

## Tech Stack

- **Python** 3.14 · **uv** (package management)
- **Typer + Rich** (CLI framework + terminal UI)
- **PyTorch + qwen-tts** (model runtime)
- **HuggingFace Hub** (model registry)
- **soundfile + scipy** (audio I/O)
- **Pydantic + pydantic-settings** (data validation + configuration)

## License

TBD

---

*Active development — APIs and commands may change between versions.*
