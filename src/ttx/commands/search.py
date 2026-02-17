"""Model search command with async size fetching and hardware compatibility."""

import asyncio
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ttx.hardware_requirements import HardwareRequirements
from ttx.models.hub import HuggingFaceHub
from ttx.models.types import format_model_size, get_model_size_async

console = Console()


def search_command(
    query: Optional[str] = None,
    limit: int = 20,
    show_compatible: bool = False,
) -> None:
    """Search for TTS models on HuggingFace Hub.

    Fetches model sizes and hardware compatibility concurrently in the
    background and updates the display as they become available.

    Args:
        query: Optional search query string.
        limit: Maximum number of results to return.
        show_compatible: If True, only show models compatible with current hardware.
    """
    try:
        # Run async implementation
        asyncio.run(
            search_command_async(query=query, limit=limit, show_compatible=show_compatible)
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


async def search_command_async(
    query: Optional[str], limit: int, show_compatible: bool
) -> None:
    """Async implementation of search with live-updating sizes and compatibility.

    Args:
        query: Optional search query string.
        limit: Maximum number of results to return.
        show_compatible: If True, only show compatible models.
    """
    # Step 1: Fetch models list (fast)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(description="Searching HuggingFace Hub...", total=None)
        hub = HuggingFaceHub()
        models = list(hub.search_models(query=query, limit=limit))  # Convert generator to list

    if not models:
        console.print("[yellow]No models found.[/yellow]")
        return

    # Initialize hardware checker
    hw_req = HardwareRequirements()

    # Show hardware info
    if hw_req.hw_info.cuda_available and hw_req._available_vram_gb:
        hw_info = (
            f"[dim]GPU: {hw_req.hw_info.gpus[0].name} | "
            f"VRAM: {hw_req._available_vram_gb:.1f} GB available[/dim]"
        )
    else:
        hw_info = "[dim]CPU-only mode (no GPU detected)[/dim]"

    console.print()
    console.print(hw_info)

    # Step 2: Create table with loading indicators
    model_count = len(models)
    table = Table(title=f"Found {model_count} TTS Models", show_lines=False)
    table.add_column("Model ID", style="cyan", no_wrap=True)
    table.add_column("Size", style="magenta", justify="right")
    table.add_column("HW", style="white", justify="center", no_wrap=True)  # Hardware compat
    table.add_column("Downloads", style="green", justify="right")
    table.add_column("Likes", style="yellow", justify="right")
    table.add_column("Modified", style="blue")

    # Store row data for updating (model, size, compat, downloads, likes, modified)
    row_data = []
    for model in models:
        row = [
            model.id,
            "[dim]...[/dim]",  # Size loading
            "[dim]?[/dim]",  # Compat loading
            f"{model.downloads:,}" if model.downloads else "0",
            f"{model.likes:,}" if model.likes else "0",
            model.last_modified.strftime("%Y-%m-%d") if model.last_modified else "Unknown",
        ]
        row_data.append(row)
        table.add_row(*row)

    console.print()

    # Step 3: Show table and fetch sizes + compatibility concurrently
    async def fetch_and_update(model_index: int, model):
        """Fetch size and compatibility for a model."""
        try:
            size_bytes = await get_model_size_async(model)
            size_str = format_model_size(size_bytes)
            
            # Check compatibility
            status = hw_req.check_compatibility(model, size_bytes)
            estimate = hw_req.estimate_vram(model, size_bytes)
            compat_str = hw_req.format_compatibility(status, estimate)
            
            return (model_index, size_str, compat_str, status)
        except Exception:
            return (model_index, "[red]Error[/red]", "[dim]?[/dim]", None)

    # Create all fetch tasks
    fetch_tasks = [fetch_and_update(i, model) for i, model in enumerate(models)]
    
    # Track which models to keep if filtering
    models_to_show = set(range(len(models)))

    # Show table with live updates
    with Live(table, console=console, refresh_per_second=4) as live:
        # Process results as they complete
        for coro in asyncio.as_completed(fetch_tasks):
            model_index, size_str, compat_str, status = await coro
            
            # Update the row data
            row_data[model_index][1] = size_str
            row_data[model_index][2] = compat_str
            
            # Apply filtering if needed
            if show_compatible and status:
                from ttx.hardware_requirements import CompatibilityStatus
                if status not in [CompatibilityStatus.FITS, CompatibilityStatus.TIGHT]:
                    models_to_show.discard(model_index)

            # Rebuild table with updated data
            filtered_count = len(models_to_show)
            title = f"Found {filtered_count} TTS Models"
            if show_compatible:
                title += " (compatible only)"
            
            new_table = Table(title=title, show_lines=False)
            new_table.add_column("Model ID", style="cyan", no_wrap=True)
            new_table.add_column("Size", style="magenta", justify="right")
            new_table.add_column("HW", style="white", justify="center", no_wrap=True)
            new_table.add_column("Downloads", style="green", justify="right")
            new_table.add_column("Likes", style="yellow", justify="right")
            new_table.add_column("Modified", style="blue")

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
    console.print("[dim]Use [bold]ttx install <model-id>[/bold] to install a model[/dim]")
