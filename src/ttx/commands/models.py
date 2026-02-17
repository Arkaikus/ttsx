"""Model management commands."""

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ttx.cache import CacheManager
from ttx.models.hub import HuggingFaceHub
from ttx.models.registry import ModelRegistry

console = Console()


def install_command(model_id: str) -> None:
    """Install a TTS model from HuggingFace Hub.

    Args:
        model_id: Model ID to install (e.g., author/model-name).
    """
    try:
        hub = HuggingFaceHub()
        registry = ModelRegistry()
        cache = CacheManager(registry=registry)

        # Check if already installed
        if registry.is_installed(model_id):
            console.print(f"[yellow]Model {model_id} is already installed.[/yellow]")
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(description=f"Downloading {model_id}...", total=None)

            # Download model
            model_path = hub.download_model(model_id)

            progress.update(task, description="Calculating size...")
            # Calculate size
            size = sum(f.stat().st_size for f in model_path.rglob("*") if f.is_file())

            progress.update(task, description="Registering model...")
            # Register model
            cache.registry.register(model_id, model_path, size)

        console.print()
        console.print(f"[green]✓[/green] Successfully installed {model_id}")
        console.print(f"[dim]Location:[/dim] {model_path}")
        console.print(f"[dim]Size:[/dim] {size / (1024**3):.2f} GB")

    except Exception as e:
        console.print(f"[red]Error installing model:[/red] {e}")
        raise


def models_command() -> None:
    """List installed TTS models."""
    try:
        registry = ModelRegistry()
        installed = registry.list()

        if not installed:
            console.print("[yellow]No models installed.[/yellow]")
            console.print()
            console.print("[dim]Search for models with:[/dim] [bold]ttx search[/bold]")
            return

        # Create table
        table = Table(title=f"{len(installed)} Installed Models", show_lines=False)
        table.add_column("Model ID", style="cyan", no_wrap=True)
        table.add_column("Size", style="green", justify="right")
        table.add_column("Installed", style="blue")
        table.add_column("Last Used", style="yellow")
        table.add_column("Pinned", style="magenta", justify="center")

        for model in installed:
            table.add_row(
                model.model_id,
                f"{model.size_gb:.2f} GB",
                model.installed_at.strftime("%Y-%m-%d"),
                model.last_used.strftime("%Y-%m-%d") if model.last_used else "Never",
                "📌" if model.is_pinned else "",
            )

        # Show cache info
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


def remove_command(model_id: str, force: bool = False) -> None:
    """Remove an installed TTS model.

    Args:
        model_id: Model ID to remove.
        force: Skip confirmation prompt.
    """
    try:
        registry = ModelRegistry()
        cache = CacheManager(registry=registry)

        # Check if installed
        if not registry.is_installed(model_id):
            console.print(f"[yellow]Model {model_id} is not installed.[/yellow]")
            return

        model = registry.get(model_id)

        # Confirm unless forced
        if not force:
            console.print(f"About to remove: [cyan]{model_id}[/cyan]")
            console.print(f"Size: {model.size_gb:.2f} GB")
            confirm = typer.confirm("Are you sure?")
            if not confirm:
                console.print("Cancelled.")
                return

        # Remove
        cache.remove(model_id)
        console.print(f"[green]✓[/green] Removed {model_id}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


def info_command(model_id: str) -> None:
    """Show detailed information about a model.

    Args:
        model_id: Model ID to get information about.
    """
    try:
        registry = ModelRegistry()
        hub = HuggingFaceHub()

        # Check if installed
        if registry.is_installed(model_id):
            model = registry.get(model_id)

            table = Table(title=f"Installed Model: {model_id}", show_header=False)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="white")

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
            # Fetch from HuggingFace
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(description=f"Fetching info for {model_id}...", total=None)
                model_info = hub.get_model_info(model_id)

            table = Table(title=f"Model: {model_id}", show_header=False)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="white")

            table.add_row("Model ID", model_info.model_id)
            table.add_row("Author", model_info.author)
            table.add_row("Size", model_info.format_size())
            table.add_row("Downloads", f"{model_info.downloads:,}")
            table.add_row("Likes", f"{model_info.likes:,}")
            table.add_row("Last Modified", model_info.last_modified.strftime("%Y-%m-%d"))
            table.add_row("Pipeline", model_info.pipeline_tag)
            if model_info.library_name:
                table.add_row("Library", model_info.library_name)

            console.print()
            console.print(table)
            console.print()
            console.print(
                f"[dim]Install with:[/dim] [bold]ttx install {model_id}[/bold]"
            )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise
