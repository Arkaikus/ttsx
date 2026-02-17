"""CLI entry point for ttsx.

This module defines the Typer app and wires up command implementations
from the commands/ folder. Keep this file minimal - business logic
belongs in commands/*.py modules.
"""

from pathlib import Path
from typing import Optional

import typer

from ttsx.commands import (
    generate_command,
    voices_command,
    hw_command,
    info_command,
    install_command,
    models_command,
    remove_command,
    search_command,
    version_command,
)

app = typer.Typer(
    name="ttsx",
    help="Modern CLI for text-to-speech generation and model management",
    no_args_is_help=True,
)


@app.command()
def hw(
    json_output: bool = typer.Option(False, "--json", help="Output hardware info as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
) -> None:
    """Display hardware information and TTS capabilities.

    Shows GPU, CPU, and memory information to help you choose
    appropriate models for your system.

    Examples:
        ttsx hw                  # Show hardware info
        ttsx hw --json          # JSON output for scripting
        ttsx hw --verbose       # Detailed diagnostics
    """
    hw_command(json_output=json_output, verbose=verbose)


@app.command()
def version() -> None:
    """Show ttsx version."""
    version_command()


@app.command()
def generate(
    text: Optional[str] = typer.Argument(None, help="Text to convert to speech (use '-' for stdin)"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model ID to use"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output WAV file path"),
    voice: Optional[str] = typer.Option(None, "--voice", "-v", help="Predefined voice name"),
    text_file: Optional[Path] = typer.Option(None, "--text-file", "-f", help="Read text from file"),
    ref_audio: Optional[Path] = typer.Option(None, "--ref-audio", help="Reference audio for voice cloning"),
    ref_text: Optional[str] = typer.Option(None, "--ref-text", help="Transcript of reference audio"),
) -> None:
    """Generate speech from text.

    Examples:
        ttsx generate "Hello world"
        ttsx generate "Hello" --output hello.wav
        ttsx generate "Hello" --voice Chelsie
        ttsx generate --text-file story.txt
        echo "Hello" | ttsx generate -
        ttsx generate "Hello" --ref-audio voice.wav --ref-text "Reference transcript"
    """
    try:
        generate_command(
            text=text,
            model_id=model,
            output=output,
            voice=voice,
            ref_audio=ref_audio,
            ref_text=ref_text,
            text_file=text_file,
        )
    except Exception:
        raise typer.Exit(1)


@app.command()
def voices(
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model ID to check"),
) -> None:
    """List available predefined voices.

    Examples:
        ttsx voices
        ttsx voices --model mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit
    """
    try:
        voices_command(model_id=model)
    except Exception:
        raise typer.Exit(1)


@app.command()
def search(
    query: Optional[str] = typer.Argument(None, help="Search query"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum number of results"),
    compatible: bool = typer.Option(
        False,
        "--compatible",
        help="Show only models compatible with your hardware",
    ),
) -> None:
    """Search for TTS models on HuggingFace Hub.

    Model sizes and hardware compatibility are fetched concurrently in the
    background and displayed as they become available.

    Examples:
        ttsx search                  # List popular TTS models
        ttsx search "qwen"           # Search for Qwen models
        ttsx search --limit 10       # Show only 10 results
        ttsx search --compatible     # Show only models that fit in VRAM
    """
    try:
        search_command(query=query, limit=limit, show_compatible=compatible)
    except Exception:
        raise typer.Exit(1)


@app.command()
def install(
    model_id: str = typer.Argument(..., help="Model ID to install (e.g., author/model-name)"),
) -> None:
    """Install a TTS model from HuggingFace Hub.

    Examples:
        ttsx install Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
        ttsx install OpenMOSS-Team/MOSS-TTS
    """
    try:
        install_command(model_id=model_id)
    except Exception:
        raise typer.Exit(1)


@app.command()
def models() -> None:
    """List installed TTS models.

    Examples:
        ttsx models
    """
    try:
        models_command()
    except Exception:
        raise typer.Exit(1)


@app.command()
def remove(
    model_id: str = typer.Argument(..., help="Model ID to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Remove an installed TTS model.

    Examples:
        ttsx remove author/model-name
        ttsx remove author/model-name --force
    """
    try:
        remove_command(model_id=model_id, force=force)
    except Exception:
        raise typer.Exit(1)


@app.command()
def info(
    model_id: str = typer.Argument(..., help="Model ID"),
) -> None:
    """Show detailed information about a model.

    Examples:
        ttsx info author/model-name
    """
    try:
        info_command(model_id=model_id)
    except Exception:
        raise typer.Exit(1)


@app.callback()
def main() -> None:
    """ttsx - Modern CLI for text-to-speech generation and model management."""
    pass


if __name__ == "__main__":
    app()
