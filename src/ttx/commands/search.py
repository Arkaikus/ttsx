"""Model search command."""

from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ttx.models.hub import HuggingFaceHub

console = Console()


def search_command(query: Optional[str] = None, limit: int = 20) -> None:
    """Search for TTS models on HuggingFace Hub.

    Args:
        query: Optional search query string.
        limit: Maximum number of results to return.
    """
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Searching HuggingFace Hub...", total=None)
            hub = HuggingFaceHub()
            models = hub.search_models(query=query, limit=limit)

        if not models:
            console.print("[yellow]No models found.[/yellow]")
            return

        # Create table with size column
        table = Table(title=f"Found {len(models)} TTS Models", show_lines=False)
        table.add_column("Model ID", style="cyan", no_wrap=True)
        table.add_column("Size", style="magenta", justify="right")
        table.add_column("Downloads", style="green", justify="right")
        table.add_column("Likes", style="yellow", justify="right")
        table.add_column("Modified", style="blue")

        for model in models:
            table.add_row(
                model.model_id,
                model.format_size(),
                f"{model.downloads:,}",
                f"{model.likes:,}",
                model.last_modified.strftime("%Y-%m-%d"),
            )

        console.print()
        console.print(table)
        console.print()
        console.print(
            "[dim]Use [bold]ttx install <model-id>[/bold] to install a model[/dim]"
        )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise
