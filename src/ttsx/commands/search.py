"""Model search command with async size fetching and hardware compatibility."""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ttsx.hardware_requirements import CompatibilityStatus, HardwareRequirements
from ttsx.models.hub import HuggingFaceHub
from ttsx.models.types import format_model_size, get_model_size_async

app = typer.Typer(help="Search for TTS models on HuggingFace Hub.")
console = Console()


@app.callback(invoke_without_command=True)
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
        ttsx search
        ttsx search "qwen"
        ttsx search --limit 10
        ttsx search --compatible
    """
    try:
        asyncio.run(_search_async(query=query, limit=limit, show_compatible=compatible))
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


async def _search_async(query: Optional[str], limit: int, show_compatible: bool) -> None:
    """Async implementation with live-updating sizes and compatibility."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(description="Searching HuggingFace Hub...", total=None)
        hub = HuggingFaceHub()
        models = list(hub.search_models(query=query, limit=limit))

    if not models:
        console.print("[yellow]No models found.[/yellow]")
        return

    hw_req = HardwareRequirements()

    if hw_req.hw_info.cuda_available and hw_req._available_vram_gb:
        hw_info = (
            f"[dim]GPU: {hw_req.hw_info.gpus[0].name} | "
            f"VRAM: {hw_req._available_vram_gb:.1f} GB available[/dim]"
        )
    else:
        hw_info = "[dim]CPU-only mode (no GPU detected)[/dim]"

    console.print()
    console.print(hw_info)

    model_count = len(models)
    table = Table(
        title=f"Found {model_count} TTS Models",
        show_lines=False,
        expand=True,
        box=None,
        padding=(0, 1),
    )
    table.add_column("Model ID", style="cyan", no_wrap=False, overflow="fold", ratio=2)
    table.add_column("Size", style="magenta", justify="right", width=10)
    table.add_column("HW", style="white", justify="center", no_wrap=True, width=10)
    table.add_column("Downloads", style="green", justify="right", width=12)
    table.add_column("Likes", style="yellow", justify="right", width=8)
    table.add_column("Modified", style="blue", width=12)

    row_data = []
    for model in models:
        row = [
            model.id,
            "[dim]...[/dim]",
            "[dim]?[/dim]",
            f"{model.downloads:,}" if model.downloads else "0",
            f"{model.likes:,}" if model.likes else "0",
            model.last_modified.strftime("%Y-%m-%d") if model.last_modified else "Unknown",
        ]
        row_data.append(row)
        table.add_row(*row)

    console.print()

    async def _fetch_one(model_index: int, model):
        try:
            size_bytes = await get_model_size_async(model)
            size_str = format_model_size(size_bytes)
            status = hw_req.check_compatibility(model, size_bytes)
            estimate = hw_req.estimate_vram(model, size_bytes)
            compat_str = hw_req.format_compatibility(status, estimate)
            return (model_index, size_str, compat_str, status)
        except Exception:
            return (model_index, "[red]Error[/red]", "[dim]?[/dim]", None)

    fetch_tasks = [_fetch_one(i, model) for i, model in enumerate(models)]
    models_to_show = set(range(len(models)))

    with Live(table, console=console, refresh_per_second=4) as live:
        for coro in asyncio.as_completed(fetch_tasks):
            model_index, size_str, compat_str, status = await coro

            row_data[model_index][1] = size_str
            row_data[model_index][2] = compat_str

            if show_compatible and status:
                if status not in [CompatibilityStatus.FITS, CompatibilityStatus.TIGHT]:
                    models_to_show.discard(model_index)

            filtered_count = len(models_to_show)
            title = f"Found {filtered_count} TTS Models"
            if show_compatible:
                title += " (compatible only)"

            new_table = Table(
                title=title,
                show_lines=False,
                expand=True,
                box=None,
                padding=(0, 1),
            )
            new_table.add_column("Model ID", style="cyan", no_wrap=False, overflow="fold", ratio=2)
            new_table.add_column("Size", style="magenta", justify="right", width=10)
            new_table.add_column("HW", style="white", justify="center", no_wrap=True, width=12)
            new_table.add_column("Downloads", style="green", justify="right", width=12)
            new_table.add_column("Likes", style="yellow", justify="right", width=8)
            new_table.add_column("Modified", style="blue", width=12)

            for idx, row in enumerate(row_data):
                if idx in models_to_show:
                    new_table.add_row(*row)

            live.update(new_table)

    console.print()
    console.print(
        "[dim]Legend: "
        "[green]✓[/green]=Fits  "
        "[yellow]⚠[/yellow]=Tight  "
        "[red]✗[/red]=Too Large  "
        "[cyan]ℹ[/cyan]=CPU  "
        "[dim]?[/dim]=Unknown[/dim]"
    )
    console.print()
    console.print("[dim]Use [bold]ttsx models install <model-id>[/bold] to install a model[/dim]")
