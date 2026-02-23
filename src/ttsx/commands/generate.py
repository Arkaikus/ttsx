"""TTS generation command."""

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ttsx.generation.engine import get_tts_engine
from ttsx.models.registry import ModelRegistry

app = typer.Typer(help="Generate speech from text.")
console = Console()


@app.callback(invoke_without_command=True)
def generate(
    text: Annotated[str | None, typer.Argument(help="Text to convert (use '-' for stdin)")] = None,
    model: Annotated[str | None, typer.Option("--model", "-m", help="Model ID to use")] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output WAV file path")
    ] = None,
    voice: Annotated[
        str | None, typer.Option("--voice", "-v", help="Predefined voice name")
    ] = None,
    text_file: Annotated[
        Path | None, typer.Option("--text-file", "-f", help="Read text from file")
    ] = None,
    ref_audio: Annotated[
        Path | None,
        typer.Option("--ref-audio", help="Reference audio for voice cloning"),
    ] = None,
    ref_text: Annotated[
        str | None, typer.Option("--ref-text", help="Transcript of reference audio")
    ] = None,
) -> None:
    """Generate speech from text.

    Examples:
        ttsx generate "Hello world"
        ttsx generate "Hello" --output hello.wav
        ttsx generate "Hello" --voice Serena
        ttsx generate --text-file story.txt
        echo "Hello" | ttsx generate -
        ttsx generate "Hello" --ref-audio voice.wav --ref-text "Reference transcript"
    """
    try:
        # ── Resolve text input ───────────────────────────────────────────────
        if text_file:
            if not text_file.exists():
                console.print(f"[red]Error:[/red] File not found: {text_file}")
                raise SystemExit(1)
            text = text_file.read_text(encoding="utf-8")
            console.print(f"[dim]Reading text from:[/dim] {text_file}")
        elif text == "-":
            console.print("[dim]Reading text from stdin...[/dim]")
            text = sys.stdin.read()
            if not text.strip():
                console.print("[red]Error:[/red] No text provided via stdin")
                raise SystemExit(1)
        elif not text:
            console.print("[red]Error:[/red] No text provided. Use argument, --text-file, or stdin")
            raise SystemExit(1)

        if ref_audio and not ref_text:
            console.print(
                "[yellow]Warning:[/yellow] --ref-audio provided without --ref-text. "
                "For best results, provide transcript of reference audio."
            )

        if ref_audio and not Path(ref_audio).exists():
            console.print(f"[red]Error:[/red] Reference audio not found: {ref_audio}")
            raise SystemExit(1)

        # ── Summary ─────────────────────────────────────────────────────────
        info_table = Table(show_header=False, box=None)
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value")

        info_table.add_row("Model", model or "[dim]Using first installed model[/dim]")
        info_table.add_row("Text length", f"{len(text)} characters")
        if voice:
            info_table.add_row("Voice", voice)
        if ref_audio:
            info_table.add_row("Voice cloning", str(ref_audio))

        console.print()
        console.print(info_table)
        console.print()

        # ── Resolve model ────────────────────────────────────────────────────
        registry = ModelRegistry()
        model_id = model
        if model_id is None:
            installed = list(registry.list_models())
            if not installed:
                console.print(
                    "[red]Error:[/red] No models installed. Install one first:\n"
                    "  [bold]ttsx models install <model-id>[/bold]"
                )
                raise SystemExit(1)
            model_id = installed[0].model_id
            console.print(f"[dim]Using installed model: {model_id}[/dim]")

        model_info = registry.get(model_id)
        if not model_info:
            console.print(
                f"[red]Error:[/red] Model '{model_id}' not installed.\n"
                f"  [bold]ttsx models install {model_id}[/bold]"
            )
            raise SystemExit(1)

        try:
            engine = get_tts_engine(model_id)
        except NotImplementedError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise SystemExit(1) from e

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
        raise SystemExit(1) from e
    except RuntimeError as e:
        console.print(f"[red]Runtime Error:[/red] {e}")
        raise SystemExit(1) from e
    except KeyboardInterrupt as e:
        console.print("\n[yellow]Generation cancelled by user[/yellow]")
        raise SystemExit(130) from e
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise
