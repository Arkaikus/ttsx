"""Voice cloning command."""

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ttsx.utils.exceptions import InvalidAudioFileError, VoiceCloningError
from ttsx.voice.cloner import clone_with_audio, clone_with_profile

app = typer.Typer(help="Clone a voice and generate speech.")
console = Console()


@app.callback(invoke_without_command=True)
def clone(
    text: Annotated[
        str | None, typer.Argument(help="Text to synthesize (use '-' for stdin)")
    ] = None,
    profile: Annotated[
        str | None, typer.Option("--profile", "-p", help="Saved voice profile name")
    ] = None,
    audio: Annotated[
        Path | None,
        typer.Option("--audio", "-a", help="Reference audio file (WAV/MP3/FLAC)"),
    ] = None,
    ref_text: Annotated[
        str | None,
        typer.Option("--ref-text", "-t", help="Transcript of reference audio (for --audio mode)"),
    ] = None,
    model: Annotated[str | None, typer.Option("--model", "-m", help="Model ID to use")] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output WAV file path")
    ] = None,
    text_file: Annotated[
        Path | None, typer.Option("--text-file", "-f", help="Read text from file")
    ] = None,
) -> None:
    """Clone a voice and generate speech.

    Provide either --profile (a saved voice profile) or --audio (a raw reference
    audio file). For best clone quality, always supply a transcript via --ref-text
    when using --audio.

    Examples:
        ttsx clone "Hello world" --profile my-voice
        ttsx clone "Hello world" --audio reference.wav
        ttsx clone "Hello world" --audio reference.wav --ref-text "Transcript here"
        ttsx clone --text-file script.txt --profile narrator --output out.wav
        echo "Hello" | ttsx clone - --profile my-voice
    """
    try:
        if text_file:
            if not text_file.exists():
                console.print(f"[red]Error:[/red] Text file not found: {text_file}")
                raise SystemExit(1)
            text = text_file.read_text(encoding="utf-8")
            console.print(f"[dim]Reading text from:[/dim] {text_file}")
        elif text == "-":
            console.print("[dim]Reading text from stdin…[/dim]")
            text = sys.stdin.read()
            if not text.strip():
                console.print("[red]Error:[/red] No text received via stdin")
                raise SystemExit(1)
        elif not text:
            console.print(
                "[red]Error:[/red] Provide text via argument, --text-file, or stdin ('-')"
            )
            raise SystemExit(1)

        if profile and audio:
            console.print("[red]Error:[/red] Use either --profile OR --audio, not both.")
            raise SystemExit(1)

        if not profile and not audio:
            console.print("[red]Error:[/red] Provide --profile <name> or --audio <file.wav>")
            raise SystemExit(1)

        summary = Table(show_header=False, box=None)
        summary.add_column("Key", style="cyan")
        summary.add_column("Value")

        summary.add_row("Text length", f"{len(text)} characters")
        if profile:
            summary.add_row("Voice profile", profile)
        else:
            summary.add_row("Reference audio", str(audio))
            summary.add_row(
                "Transcript",
                f"{len(ref_text)} chars provided"
                if ref_text
                else "[yellow]None (x-vector mode)[/yellow]",
            )
        summary.add_row("Model", model or "[dim]auto-select[/dim]")

        console.print()
        console.print(summary)
        console.print()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Cloning voice and generating speech…", total=None)

            if profile:
                output_path = clone_with_profile(
                    text=text,
                    profile_name=profile,
                    model_id=model,
                    output_path=output,
                )
                clone_warnings: list[str] = []
            else:
                assert audio is not None
                output_path, clone_warnings = clone_with_audio(
                    text=text,
                    audio_path=audio,
                    model_id=model,
                    ref_text=ref_text,
                    output_path=output,
                )

        for w in clone_warnings:
            console.print(f"[yellow]Warning:[/yellow] {w}")

        console.print()
        console.print(
            Panel(
                f"[green]✓[/green] Voice cloning complete!\n\n"
                f"[bold]{output_path}[/bold]\n\n"
                f"[dim]Play with: ffplay {output_path}[/dim]",
                title="Clone Complete",
                border_style="green",
            )
        )

    except (VoiceCloningError, InvalidAudioFileError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from e
    except RuntimeError as e:
        console.print(f"[red]Runtime Error:[/red] {e}")
        raise SystemExit(1) from e
    except KeyboardInterrupt as e:
        console.print("\n[yellow]Cancelled by user[/yellow]")
        raise SystemExit(130) from e
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise
