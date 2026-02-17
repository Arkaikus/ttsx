"""TTS generation command."""

import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ttsx.generation.engine import get_tts_engine
from ttsx.models.registry import ModelRegistry

console = Console()


def generate_command(
    text: Optional[str] = None,
    model_id: Optional[str] = None,
    output: Optional[Path] = None,
    voice: Optional[str] = None,
    ref_audio: Optional[Path] = None,
    ref_text: Optional[str] = None,
    text_file: Optional[Path] = None,
) -> None:
    """Generate speech from text.

    Args:
        text: Text to convert to speech (or "-" for stdin)
        model_id: Model ID to use (uses first installed if None)
        output: Output WAV file path
        voice: Predefined voice name
        ref_audio: Reference audio for voice cloning
        ref_text: Reference audio transcript
        text_file: Read text from file
    """
    try:
        # Determine text source
        if text_file:
            # Read from file
            if not text_file.exists():
                console.print(f"[red]Error:[/red] File not found: {text_file}")
                raise SystemExit(1)
            text = text_file.read_text(encoding="utf-8")
            console.print(f"[dim]Reading text from:[/dim] {text_file}")
        elif text == "-":
            # Read from stdin
            console.print("[dim]Reading text from stdin...[/dim]")
            text = sys.stdin.read()
            if not text.strip():
                console.print("[red]Error:[/red] No text provided via stdin")
                raise SystemExit(1)
        elif not text:
            console.print("[red]Error:[/red] No text provided. Use --text, --text-file, or stdin")
            raise SystemExit(1)

        # Validate voice cloning params
        if ref_audio and not ref_text:
            console.print(
                "[yellow]Warning:[/yellow] --ref-audio provided without --ref-text. "
                "For best results, provide transcript of reference audio."
            )

        if ref_audio and not Path(ref_audio).exists():
            console.print(f"[red]Error:[/red] Reference audio not found: {ref_audio}")
            raise SystemExit(1)

        # Show generation info
        info_table = Table(show_header=False, box=None)
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value")

        if model_id:
            info_table.add_row("Model", model_id)
        else:
            info_table.add_row("Model", "[dim]Using first installed model[/dim]")

        info_table.add_row("Text length", f"{len(text)} characters")

        if voice:
            info_table.add_row("Voice", voice)
        if ref_audio:
            info_table.add_row("Voice cloning", f"{ref_audio}")

        console.print()
        console.print(info_table)
        console.print()

        # Determine which model to use
        registry = ModelRegistry()
        if model_id is None:
            # Use first installed model
            installed = list(registry.list_models())
            if not installed:
                console.print(
                    "[red]Error:[/red] No models installed. Install a model first with: "
                    "[bold]ttsx install <model-id>[/bold]"
                )
                raise SystemExit(1)
            model_id = installed[0].model_id
            console.print(f"[dim]Using installed model: {model_id}[/dim]")

        # Verify model is installed
        model_info = registry.get(model_id)
        if not model_info:
            console.print(
                f"[red]Error:[/red] Model '{model_id}' not installed. "
                f"Install it with: [bold]ttsx install {model_id}[/bold]"
            )
            raise SystemExit(1)

        # Get appropriate engine for this model
        try:
            engine = get_tts_engine(model_id)
        except NotImplementedError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise SystemExit(1)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Generating speech...", total=None)

            output_path = engine.generate(
                text=text,
                model_id=model_id,
                model_path=model_info.path,
                output_path=output,
                voice=voice,
                ref_audio=ref_audio,
                ref_text=ref_text,
            )

        # Success message
        console.print()
        console.print(
            Panel(
                f"[green]✓[/green] Audio generated successfully!\n\n"
                f"[bold]{output_path}[/bold]\n\n"
                f"[dim]Play with: ffplay {output_path}[/dim]",
                title="Generation Complete",
                border_style="green",
            )
        )

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)
    except RuntimeError as e:
        console.print(f"[red]Runtime Error:[/red] {e}")
        raise SystemExit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Generation cancelled by user[/yellow]")
        raise SystemExit(130)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise


def voices_command(model_id: Optional[str] = None) -> None:
    """List available predefined voices for a model.

    Args:
        model_id: Model ID to check (uses first installed if None)
    """
    try:
        # Determine which model to use
        registry = ModelRegistry()
        if model_id is None:
            # Use first installed model
            installed = list(registry.list_models())
            if not installed:
                console.print(
                    "[red]Error:[/red] No models installed. Install a model first with: "
                    "[bold]ttsx install <model-id>[/bold]"
                )
                raise SystemExit(1)
            model_id = installed[0].model_id

        # Get appropriate engine for this model
        try:
            engine = get_tts_engine(model_id)
        except NotImplementedError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise SystemExit(1)

        voices = engine.list_available_voices()

        if not voices:
            console.print("[yellow]No predefined voices available for this model[/yellow]")
            return

        console.print()
        console.print(f"[bold]Available Voices[/bold] (Model: {model_id})")
        console.print()

        for voice in voices:
            console.print(f"  • {voice}")

        console.print()
        console.print(
            f"[dim]Use with: [bold]ttsx generate 'text' --voice <name>[/bold][/dim]"
        )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise
