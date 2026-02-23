"""Voice profile management commands."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ttsx.generation.engine import get_tts_engine
from ttsx.models.registry import ModelRegistry
from ttsx.utils.exceptions import VoiceCloningError
from ttsx.voice.encoder import SUPPORTED_FORMATS, check_cloning_suitability, get_audio_info
from ttsx.voice.profiles import VoiceProfileManager

app = typer.Typer(help="Manage saved voice profiles for cloning.", no_args_is_help=True)
console = Console()


@app.command("list")
def list_profiles(
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Model to show predefined voices for"),
    ] = None,
    predefined: Annotated[
        bool, typer.Option("--predefined", help="Also show built-in model voices")
    ] = False,
) -> None:
    """List saved voice profiles.

    Examples:
        ttsx voices list
        ttsx voices list --predefined
        ttsx voices list --predefined --model Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
    """
    manager = VoiceProfileManager()
    profiles = manager.list_profiles()

    console.print()

    if profiles:
        table = Table(
            title="[bold]Saved Voice Profiles[/bold]",
            show_header=True,
            header_style="bold cyan",
            expand=True,
            box=None,
            padding=(0, 1),
        )
        table.add_column("Name", style="bold")
        table.add_column("Audio")
        table.add_column("Language")
        table.add_column("Has Transcript", justify="center")
        table.add_column("Description")
        table.add_column("Created")

        for profile in profiles:
            audio_label = (
                str(profile.audio_path.name)
                if profile.audio_exists
                else f"[red]MISSING[/red] {profile.audio_path.name}"
            )
            table.add_row(
                profile.name,
                audio_label,
                profile.language or "[dim]—[/dim]",
                "[green]✓[/green]" if profile.ref_text else "[dim]✗[/dim]",
                profile.description or "[dim]—[/dim]",
                profile.format_created(),
            )

        console.print(table)
        console.print()
        console.print(
            "[dim]Use a profile:[/dim] [bold]ttsx clone --profile <name> 'your text'[/bold]"
        )
    else:
        console.print("[yellow]No saved voice profiles.[/yellow]")
        console.print(
            "\n[dim]Add a profile with:[/dim] [bold]ttsx voices add <name> <audio.wav>[/bold]"
        )

    if predefined:
        console.print()
        registry = ModelRegistry()
        model_id = model

        if model_id is None:
            installed = list(registry.list_models())
            if not installed:
                console.print(
                    "[yellow]No models installed – cannot show predefined voices.[/yellow]"
                )
                return
            model_id = installed[0].model_id

        try:
            engine = get_tts_engine(model_id)
        except NotImplementedError as e:
            console.print(f"[red]Error:[/red] {e}")
            return

        built_in = engine.list_available_voices()
        if built_in:
            pred_table = Table(
                title=f"[bold]Predefined Voices[/bold] — {model_id}",
                show_header=False,
                box=None,
            )
            pred_table.add_column("Voice", style="cyan")
            for v in built_in:
                pred_table.add_row(f"• {v}")
            console.print(pred_table)
            console.print()
            console.print(
                "[dim]Use a predefined voice:[/dim] "
                "[bold]ttsx generate 'text' --voice <name>[/bold]"
            )

    console.print()


@app.command("add")
def add_profile(
    name: Annotated[str, typer.Argument(help="Unique profile name")],
    audio_file: Annotated[Path, typer.Argument(help="Reference audio file (WAV/MP3/FLAC)")],
    ref_text: Annotated[
        str | None,
        typer.Option("--ref-text", "-t", help="Transcript of reference audio (recommended)"),
    ] = None,
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Optional description")
    ] = None,
    language: Annotated[
        str | None,
        typer.Option("--language", "-l", help="Language of the voice (e.g. English)"),
    ] = None,
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Replace existing profile with the same name")
    ] = False,
) -> None:
    """Save a voice profile from a reference audio file.

    Examples:
        ttsx voices add my-voice reference.wav
        ttsx voices add my-voice reference.wav --ref-text "Hello, this is my voice."
        ttsx voices add narrator clip.mp3 --language English --description "Deep narrator"
    """
    if not audio_file.exists():
        console.print(f"[red]Error:[/red] Audio file not found: {audio_file}")
        raise SystemExit(1)

    suffix = audio_file.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        console.print(
            f"[red]Error:[/red] Unsupported format: {suffix}\n"
            f"Supported: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )
        raise SystemExit(1)

    for w in check_cloning_suitability(audio_file):
        console.print(f"[yellow]Warning:[/yellow] {w}")

    info = get_audio_info(audio_file)
    console.print()
    info_table = Table(show_header=False, box=None)
    info_table.add_column("Key", style="cyan")
    info_table.add_column("Value")
    info_table.add_row("Profile name", name)
    info_table.add_row("Source audio", str(audio_file))
    info_table.add_row("Duration", f"{info.get('duration', 0):.1f}s")
    info_table.add_row("Sample rate", f"{info.get('sample_rate', '?')} Hz")
    if language:
        info_table.add_row("Language", language)
    if description:
        info_table.add_row("Description", description)
    info_table.add_row(
        "Has transcript", "[green]Yes[/green]" if ref_text else "[yellow]No[/yellow]"
    )
    console.print(info_table)
    console.print()

    if not ref_text:
        console.print(
            "[yellow]Tip:[/yellow] Providing --ref-text significantly improves clone quality. "
            "Without it the model runs in x-vector mode."
        )
        console.print()

    try:
        manager = VoiceProfileManager()
        profile = manager.add(
            name=name,
            audio_file=audio_file,
            ref_text=ref_text,
            description=description,
            language=language,
            overwrite=overwrite,
        )
    except VoiceCloningError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from e

    console.print(
        Panel(
            f"[green]✓[/green] Voice profile [bold]{profile.name}[/bold] saved!\n\n"
            f"Audio stored at: [dim]{profile.audio_path}[/dim]\n\n"
            f"Clone a voice:\n"
            f"  [bold]ttsx clone --profile {profile.name} 'Hello world'[/bold]",
            title="Profile Added",
            border_style="green",
        )
    )


@app.command("remove")
def remove_profile(
    name: Annotated[str, typer.Argument(help="Profile name to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation prompt")] = False,
) -> None:
    """Remove a saved voice profile.

    Examples:
        ttsx voices remove my-voice
        ttsx voices remove my-voice --force
    """
    manager = VoiceProfileManager()
    profile = manager.get(name)

    if profile is None:
        console.print(f"[red]Error:[/red] Voice profile '{name}' not found.")
        available = [p.name for p in manager.list_profiles()]
        if available:
            console.print(f"Available profiles: {', '.join(available)}")
        raise SystemExit(1)

    if not force:
        console.print(f"Remove voice profile [bold]{name}[/bold]? (audio file will be deleted)")
        if not typer.confirm("Continue?"):
            console.print("[yellow]Cancelled.[/yellow]")
            raise SystemExit(0)

    if manager.remove(name):
        console.print(f"[green]✓[/green] Voice profile [bold]{name}[/bold] removed.")
    else:
        console.print(f"[red]Error:[/red] Could not remove profile '{name}'.")
        raise SystemExit(1)


@app.command("info")
def profile_info(
    name: Annotated[str, typer.Argument(help="Profile name to inspect")],
) -> None:
    """Show detailed information about a saved voice profile.

    Examples:
        ttsx voices info my-voice
    """
    manager = VoiceProfileManager()
    profile = manager.get(name)

    if profile is None:
        console.print(f"[red]Error:[/red] Voice profile '{name}' not found.")
        raise SystemExit(1)

    audio_status = "[green]Available[/green]" if profile.audio_exists else "[red]MISSING[/red]"

    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column("Key", style="cyan", no_wrap=True)
    info_table.add_column("Value")

    info_table.add_row("Name", profile.name)
    info_table.add_row("Audio status", audio_status)
    info_table.add_row("Audio path", str(profile.audio_path))

    if profile.audio_exists:
        audio_info = get_audio_info(profile.audio_path)
        info_table.add_row("Duration", f"{audio_info.get('duration', 0):.1f}s")
        info_table.add_row("Sample rate", f"{audio_info.get('sample_rate', '?')} Hz")
        info_table.add_row("Channels", str(audio_info.get("channels", "?")))

    info_table.add_row("Language", profile.language or "[dim]not set[/dim]")
    info_table.add_row("Description", profile.description or "[dim]not set[/dim]")
    info_table.add_row(
        "Transcript",
        f"[green]Yes[/green] ({len(profile.ref_text)} chars)"
        if profile.ref_text
        else "[yellow]No (x-vector mode)[/yellow]",
    )
    info_table.add_row("Created", profile.format_created())

    console.print()
    console.print(
        Panel(info_table, title=f"[bold]Voice Profile: {name}[/bold]", border_style="cyan")
    )

    if profile.ref_text:
        console.print()
        console.print("[bold cyan]Reference transcript:[/bold cyan]")
        preview = profile.ref_text[:300]
        if len(profile.ref_text) > 300:
            preview += "…"
        console.print(f"  [dim]{preview}[/dim]")

    console.print()
    console.print(f"[dim]Clone voice:[/dim] [bold]ttsx clone --profile {name} 'your text'[/bold]")
    console.print()
