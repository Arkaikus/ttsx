"""Model management commands grouped under the 'models' sub-app."""

import typer
from rich.console import Console
from rich.progress import BarColumn, DownloadColumn, Progress, SpinnerColumn, TextColumn, TimeRemainingColumn, TransferSpeedColumn
from rich.table import Table

from pathlib import Path

from ttsx.utils.decorators import run_async
from ttsx.cache import CacheManager
from ttsx.hardware_requirements import HardwareRequirements
from ttsx.models.hub import HuggingFaceHub
from ttsx.models.registry import ModelRegistry
from ttsx.models.types import format_model_size, get_model_size

app = typer.Typer(help="Manage installed TTS models.")
console = Console()


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context) -> None:
    """Manage installed TTS models.

    Run without a subcommand to list installed models.

    Examples:
        ttsx models                              # list installed models
        ttsx models install Qwen/Qwen3-TTS-...  # install a model
        ttsx models remove Qwen/Qwen3-TTS-...   # remove a model
        ttsx models info Qwen/Qwen3-TTS-...     # show model details
    """
    if ctx.invoked_subcommand is None:
        list_models()


@app.command("list")
def list_models() -> None:
    """List installed TTS models."""
    try:
        registry = ModelRegistry()
        installed = registry.list_models()

        if not installed:
            console.print("[yellow]No models installed.[/yellow]")
            console.print()
            console.print("[dim]Search for models with:[/dim] [bold]ttsx search[/bold]")
            return

        table = Table(
            title=f"{len(installed)} Installed Models",
            show_lines=False,
            expand=True,
            box=None,
            padding=(0, 1),
        )
        table.add_column("Model ID", style="cyan", no_wrap=False, overflow="fold", ratio=3)
        table.add_column("Size", style="green", justify="right", width=10)
        table.add_column("Installed", style="blue", width=12)
        table.add_column("Last Used", style="yellow", width=12)
        table.add_column("Pinned", style="magenta", justify="center", width=8)

        for model in installed:
            table.add_row(
                model.model_id,
                f"{model.size_gb:.2f} GB",
                model.installed_at.strftime("%Y-%m-%d"),
                model.last_used.strftime("%Y-%m-%d") if model.last_used else "Never",
                "📌" if model.is_pinned else "",
            )

        cache = CacheManager(registry=registry)
        cache_info = cache.get_cache_info()

        console.print()
        console.print(table)
        console.print()
        console.print(
            f"[dim]Cache:[/dim] {cache_info['total_size_gb']:.2f} GB / "
            f"{cache_info['max_size_gb']} GB "
            f"({cache_info['usage_percent']:.1f}% used)"
        )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


@app.command("install")
@run_async
async def install(
    model_id: str = typer.Argument(..., help="Model ID to install (e.g., Qwen/Qwen3-TTS-...)"),
) -> None:
    """Install a TTS model from HuggingFace Hub.

    Examples:
        ttsx models install Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
        ttsx models install OpenMOSS-Team/MOSS-TTS
    """
    try:
        hub = HuggingFaceHub()
        registry = ModelRegistry()

        if registry.is_installed(model_id):
            console.print(f"[yellow]Model {model_id} is already installed.[/yellow]")
            return

        # Fetch metadata so the user knows what is coming.
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as p:
            p.add_task(description=f"Fetching metadata for {model_id}…", total=None)
            model_info = hub.get_model_info(model_id)

        siblings = model_info.siblings or []
        if not siblings:
            console.print(f"[red]Error:[/red] No siblings found in model info {model_id}")
            return
        
        total_bytes = sum(s.size or 0 for s in siblings)

        summary = Table(show_header=False, box=None)
        summary.add_column("Key", style="cyan")
        summary.add_column("Value")
        summary.add_row("Model", model_id)
        summary.add_row("Files", str(len(siblings)))
        if total_bytes:
            summary.add_row("Size", f"~{total_bytes / 1024 ** 3:.2f} GB")
        console.print()
        console.print(summary)
        console.print()

        # One Rich task per file; on_progress is called from download worker threads.
        # Rich Progress is thread-safe so concurrent updates work without locking.
        task_ids: dict[str, int] = {}

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description:<50}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            for sibling in siblings:
                task_ids[sibling.rfilename] = progress.add_task(
                    Path(sibling.rfilename).name,
                    total=sibling.size or None,
                )

            def on_progress(filename: str, done: int, total: int) -> None:
                if filename not in task_ids:
                    task_ids[filename] = progress.add_task(
                        Path(filename).name, total=total or None
                    )
                progress.update(task_ids[filename], completed=done, total=total or None)

            model_path = await hub.download_model(
                model_id, on_progress=on_progress, model_info=model_info
            )

        size = sum(f.stat().st_size for f in model_path.rglob("*") if f.is_file())
        CacheManager(registry=registry).registry.register(model_id, model_path, size)

        console.print()
        console.print(f"[green]✓[/green] Successfully installed [bold]{model_id}[/bold]")
        console.print(f"[dim]Location:[/dim] {model_path}")
        console.print(f"[dim]Size:[/dim] {size / 1024 ** 3:.2f} GB")

    except Exception as e:
        console.print(f"[red]Error installing model:[/red] {e}")
        raise


@app.command("remove")
def remove(
    model_id: str = typer.Argument(..., help="Model ID to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Remove an installed TTS model.

    Examples:
        ttsx models remove Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
        ttsx models remove Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice --force
    """
    try:
        registry = ModelRegistry()
        cache = CacheManager(registry=registry)

        if not registry.is_installed(model_id):
            console.print(f"[yellow]Model {model_id} is not installed.[/yellow]")
            return

        model = registry.get(model_id)

        if not force:
            console.print(f"About to remove: [cyan]{model_id}[/cyan]")
            console.print(f"Size: {model.size_gb:.2f} GB")
            if not typer.confirm("Are you sure?"):
                console.print("Cancelled.")
                return

        cache.remove(model_id)
        console.print(f"[green]✓[/green] Removed {model_id}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


@app.command("info")
def info(
    model_id: str = typer.Argument(..., help="Model ID"),
) -> None:
    """Show detailed information about a model.

    Examples:
        ttsx models info Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
    """
    try:
        registry = ModelRegistry()
        hub = HuggingFaceHub()

        if registry.is_installed(model_id):
            model = registry.get(model_id)

            table = Table(
                title=f"Installed Model: {model_id}",
                show_header=False,
                expand=True,
                box=None,
                padding=(0, 1),
            )
            table.add_column("Property", style="cyan", width=15)
            table.add_column("Value", style="white", no_wrap=False, overflow="fold")

            table.add_row("Model ID", model.model_id)
            table.add_row("Path", str(model.path))
            table.add_row("Size", f"{model.size_gb:.2f} GB")
            table.add_row("Installed", model.installed_at.strftime("%Y-%m-%d %H:%M:%S"))
            table.add_row(
                "Last Used",
                model.last_used.strftime("%Y-%m-%d %H:%M:%S") if model.last_used else "Never",
            )
            table.add_row("Pinned", "Yes" if model.is_pinned else "No")

            console.print()
            console.print(table)

        else:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(description=f"Fetching info for {model_id}...", total=None)
                model_info = hub.get_model_info(model_id)

            table = Table(
                title=f"Model: {model_id}",
                show_header=False,
                expand=True,
                box=None,
                padding=(0, 1),
            )
            table.add_column("Property", style="cyan", width=15)
            table.add_column("Value", style="white", no_wrap=False, overflow="fold")

            size_bytes = get_model_size(model_info, fetch_accurate=True)

            table.add_row("Model ID", model_info.id)
            table.add_row("Author", model_info.author or "Unknown")
            table.add_row("Size", format_model_size(size_bytes))
            table.add_row(
                "Downloads", f"{model_info.downloads:,}" if model_info.downloads else "0"
            )
            table.add_row("Likes", f"{model_info.likes:,}" if model_info.likes else "0")
            table.add_row(
                "Last Modified",
                model_info.last_modified.strftime("%Y-%m-%d")
                if model_info.last_modified
                else "Unknown",
            )
            table.add_row("Pipeline", model_info.pipeline_tag or "text-to-speech")
            if model_info.library_name:
                table.add_row("Library", model_info.library_name)

            console.print()
            console.print(table)

            hw_req = HardwareRequirements()
            if hw_req.hw_info.cuda_available and hw_req._available_vram_gb:
                console.print()
                hw_table = Table(
                    title="Hardware Compatibility",
                    show_header=False,
                    expand=True,
                    box=None,
                    padding=(0, 1),
                )
                hw_table.add_column("Property", style="cyan", width=15)
                hw_table.add_column("Value", no_wrap=False, overflow="fold")

                hw_table.add_row(
                    "Your GPU",
                    f"{hw_req.hw_info.gpus[0].name} ({hw_req._available_vram_gb:.1f} GB VRAM)",
                )

                status = hw_req.check_compatibility(model_info, size_bytes)
                estimate = hw_req.estimate_vram(model_info, size_bytes)

                if estimate:
                    hw_table.add_row(
                        "Estimated VRAM",
                        f"{estimate.estimated_vram_gb:.1f} GB ({estimate.precision.value})",
                    )
                    hw_table.add_row(
                        "Compatibility", hw_req.format_compatibility(status, estimate)
                    )

                    if not estimate.fits:
                        over = estimate.estimated_vram_gb - estimate.available_vram_gb
                        hw_table.add_row("Exceeds by", f"[red]{over:.1f} GB[/red]")

                        suggestions = hw_req.find_quantized_versions(model_info)
                        if suggestions:
                            hw_table.add_row(
                                "Try instead",
                                "\n".join(f"[dim]• {s}[/dim]" for s in suggestions),
                            )

                console.print(hw_table)

            console.print()
            console.print(
                f"[dim]Install with:[/dim] [bold]ttsx models install {model_id}[/bold]"
            )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise
