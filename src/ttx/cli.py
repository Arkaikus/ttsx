"""CLI entry point for ttx.

This module defines the Typer app and wires up command implementations
from the commands/ folder. Keep this file minimal - business logic
belongs in commands/*.py modules.
"""

from typing import Optional

import typer

from ttx.commands import (
    hw_command,
    info_command,
    install_command,
    models_command,
    remove_command,
    search_command,
    version_command,
)

app = typer.Typer(
    name="ttx",
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
        ttx hw                  # Show hardware info
        ttx hw --json          # JSON output for scripting
        ttx hw --verbose       # Detailed diagnostics
    """
    hw_command(json_output=json_output, verbose=verbose)


@app.command()
def version() -> None:
    """Show ttx version."""
    version_command()


@app.command()
def search(
    query: Optional[str] = typer.Argument(None, help="Search query"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum number of results"),
) -> None:
    """Search for TTS models on HuggingFace Hub.

    Examples:
        ttx search              # List popular TTS models
        ttx search "qwen"       # Search for Qwen models
        ttx search --limit 10   # Show only 10 results
    """
    try:
        search_command(query=query, limit=limit)
    except Exception:
        raise typer.Exit(1)


@app.command()
def install(
    model_id: str = typer.Argument(..., help="Model ID to install (e.g., author/model-name)"),
) -> None:
    """Install a TTS model from HuggingFace Hub.

    Examples:
        ttx install Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
        ttx install OpenMOSS-Team/MOSS-TTS
    """
    try:
        install_command(model_id=model_id)
    except Exception:
        raise typer.Exit(1)


@app.command()
def models() -> None:
    """List installed TTS models.

    Examples:
        ttx models
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
        ttx remove author/model-name
        ttx remove author/model-name --force
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
        ttx info author/model-name
    """
    try:
        info_command(model_id=model_id)
    except Exception:
        raise typer.Exit(1)


@app.callback()
def main() -> None:
    """ttx - Modern CLI for text-to-speech generation and model management."""
    pass


if __name__ == "__main__":
    app()
