"""Model search command with async size fetching."""

import asyncio
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ttx.models.hub import HuggingFaceHub
from ttx.models.types import format_model_size, get_model_size_async

console = Console()


def search_command(query: Optional[str] = None, limit: int = 20) -> None:
    """Search for TTS models on HuggingFace Hub.

    Fetches model sizes concurrently in the background and updates
    the display as they become available.

    Args:
        query: Optional search query string.
        limit: Maximum number of results to return.
    """
    try:
        # Run async implementation
        asyncio.run(search_command_async(query=query, limit=limit))
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


async def search_command_async(query: Optional[str], limit: int) -> None:
    """Async implementation of search with live-updating sizes.

    Args:
        query: Optional search query string.
        limit: Maximum number of results to return.
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

    # Step 2: Create table with loading indicators
    model_count = len(models) if isinstance(models, list) else "some"
    table = Table(title=f"Found {model_count} TTS Models", show_lines=False)
    table.add_column("Model ID", style="cyan", no_wrap=True)
    table.add_column("Size", style="magenta", justify="right")
    table.add_column("Downloads", style="green", justify="right")
    table.add_column("Likes", style="yellow", justify="right")
    table.add_column("Modified", style="blue")

    # Store row data for updating
    row_data = []
    for model in models:
        row = [
            model.id,
            "[dim]Loading...[/dim]",  # Initial loading state
            f"{model.downloads:,}" if model.downloads else "0",
            f"{model.likes:,}" if model.likes else "0",
            model.last_modified.strftime("%Y-%m-%d") if model.last_modified else "Unknown",
        ]
        row_data.append(row)
        table.add_row(*row)

    console.print()

    # Step 3: Show table and fetch sizes concurrently
    async def fetch_and_update_size(model_index: int, model):
        """Fetch size for a model and return index + size."""
        try:
            size_bytes = await get_model_size_async(model)
            return (model_index, format_model_size(size_bytes))
        except Exception:
            return (model_index, "[red]Error[/red]")

    # Create all fetch tasks
    fetch_tasks = [fetch_and_update_size(i, model) for i, model in enumerate(models)]

    # Show table with live updates as sizes load
    with Live(table, console=console, refresh_per_second=4) as live:
        # Process results as they complete
        for coro in asyncio.as_completed(fetch_tasks):
            model_index, size_str = await coro
            
            # Update the row data
            row_data[model_index][1] = size_str

            # Rebuild table with updated data
            new_table = Table(title=f"Found {model_count} TTS Models", show_lines=False)
            new_table.add_column("Model ID", style="cyan", no_wrap=True)
            new_table.add_column("Size", style="magenta", justify="right")
            new_table.add_column("Downloads", style="green", justify="right")
            new_table.add_column("Likes", style="yellow", justify="right")
            new_table.add_column("Modified", style="blue")

            for row in row_data:
                new_table.add_row(*row)

            live.update(new_table)

    console.print()
    console.print("[dim]Use [bold]ttx install <model-id>[/bold] to install a model[/dim]")
