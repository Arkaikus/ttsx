"""CLI commands for ttx."""

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ttx.cache import CacheManager
from ttx.hardware import HardwareDetector
from ttx.models.hub import HuggingFaceHub
from ttx.models.registry import ModelRegistry

app = typer.Typer(
    name="ttx",
    help="Modern CLI for text-to-speech generation and model management",
    no_args_is_help=True,
)
console = Console()


@app.command()
def hw(
    json_output: bool = typer.Option(
        False, "--json", help="Output hardware info as JSON"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
) -> None:
    """Display hardware information and TTS capabilities.

    Shows GPU, CPU, and memory information to help you choose
    appropriate models for your system.

    Examples:
        ttx hw                  # Show hardware info
        ttx hw --json          # JSON output for scripting
        ttx hw --verbose       # Detailed diagnostics
    """
    detector = HardwareDetector()
    info = detector.detect()

    if json_output:
        import json

        data = {
            "device_type": info.device_type,
            "cuda_available": info.cuda_available,
            "cuda_version": info.cuda_version,
            "mps_available": info.mps_available,
            "gpus": [
                {
                    "name": gpu.name,
                    "index": gpu.index,
                    "compute_capability": gpu.compute_capability,
                    "memory": {
                        "total_gb": gpu.memory.total_gb,
                        "available_gb": gpu.memory.available_gb,
                        "used_gb": gpu.memory.used_gb,
                    },
                }
                for gpu in info.gpus
            ],
            "cpu": {
                "model": info.cpu_model,
                "cores": info.cpu_cores,
                "threads": info.cpu_threads,
            },
            "ram": {
                "total_gb": info.ram_total_gb,
                "available_gb": info.ram_available_gb,
            },
            "pytorch": {
                "version": info.pytorch_version,
                "cuda_version": info.pytorch_cuda_version,
            },
        }
        console.print_json(json.dumps(data, indent=2))
        return

    # Create compute info table
    compute_table = Table(title="Compute", show_header=False, title_style="bold cyan")
    compute_table.add_column("Property", style="cyan", width=15)
    compute_table.add_column("Value", style="white")

    if info.cuda_available:
        compute_table.add_row("Device", "[bold green]CUDA GPU[/bold green]")
        for gpu in info.gpus:
            compute_table.add_row("GPU Model", gpu.name)
            if gpu.index > 0 or len(info.gpus) > 1:
                compute_table.add_row("GPU Index", str(gpu.index))
            compute_table.add_row(
                "VRAM",
                f"{gpu.memory.total_gb:.1f} GB total / "
                f"[bold green]{gpu.memory.available_gb:.1f} GB[/bold green] available",
            )
            if verbose:
                compute_table.add_row("VRAM Used", f"{gpu.memory.used_gb:.1f} GB")
            if gpu.compute_capability:
                compute_table.add_row(
                    "Compute Cap.",
                    f"{gpu.compute_capability[0]}.{gpu.compute_capability[1]}",
                )
        compute_table.add_row("CUDA Version", info.cuda_version or "N/A")
    elif info.mps_available:
        compute_table.add_row("Device", "[bold green]Apple Metal (MPS)[/bold green]")
        compute_table.add_row("Info", "GPU acceleration available via Metal")
    else:
        compute_table.add_row("Device", "[bold yellow]CPU only[/bold yellow]")
        compute_table.add_row(
            "⚠ Warning",
            "[yellow]No GPU detected - generation will be slower[/yellow]",
        )

    # Create CPU info table
    cpu_table = Table(title="CPU", show_header=False, title_style="bold cyan")
    cpu_table.add_column("Property", style="cyan", width=15)
    cpu_table.add_column("Value", style="white")
    cpu_table.add_row("Model", info.cpu_model)
    cpu_table.add_row(
        "Cores", f"{info.cpu_cores} physical / {info.cpu_threads} logical"
    )
    cpu_table.add_row(
        "RAM",
        f"{info.ram_total_gb:.1f} GB total / "
        f"[bold green]{info.ram_available_gb:.1f} GB[/bold green] available",
    )

    # Create software info table
    sw_table = Table(title="Software", show_header=False, title_style="bold cyan")
    sw_table.add_column("Property", style="cyan", width=15)
    sw_table.add_column("Value", style="white")
    sw_table.add_row("PyTorch", info.pytorch_version)
    if info.pytorch_cuda_version:
        sw_table.add_row("Build", f"CUDA {info.pytorch_cuda_version}")
    else:
        sw_table.add_row("Build", "CPU")
    sw_table.add_row("Default Device", f"[bold]{info.device_type}[/bold]")

    # Display all tables
    console.print()
    console.print(compute_table)
    console.print()
    console.print(cpu_table)
    console.print()
    console.print(sw_table)

    # Recommendations
    if info.cuda_available and info.gpus:
        vram_gb = info.gpus[0].memory.available_gb
        recommendations = detector.recommend_models(vram_gb)

        console.print()
        console.print(
            Panel.fit(
                f"[bold green]✓[/bold green] Your hardware can run: {recommendations[0]}\n"
                f"[bold green]✓[/bold green] GPU acceleration available\n"
                + (
                    "[bold blue]ℹ[/bold blue]  Consider using FP16/quantized models for better fit"
                    if vram_gb < 8
                    else f"[bold blue]ℹ[/bold blue]  {recommendations[1]}"
                ),
                title="[bold]Recommendations[/bold]",
                border_style="green",
            )
        )
    elif info.mps_available:
        console.print()
        console.print(
            Panel.fit(
                "[bold green]✓[/bold green] Apple Silicon GPU available\n"
                "[bold blue]ℹ[/bold blue]  MPS acceleration supported for compatible models",
                title="[bold]Recommendations[/bold]",
                border_style="green",
            )
        )
    else:
        console.print()
        console.print(
            Panel.fit(
                f"[bold yellow]⚠[/bold yellow]  Running on CPU - generation will be slower\n"
                f"[bold blue]ℹ[/bold blue]  Available RAM: {info.ram_available_gb:.1f} GB\n"
                "[bold blue]ℹ[/bold blue]  Consider using smaller models (<1B parameters)",
                title="[bold]Recommendations[/bold]",
                border_style="yellow",
            )
        )
    console.print()


@app.command()
def version() -> None:
    """Show ttx version."""
    from ttx import __version__

    console.print(f"ttx version [bold]{__version__}[/bold]")


@app.command()
def search(
    query: Optional[str] = typer.Argument(None, help="Search query"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum number of results"),
) -> None:
    """Search for TTS models on HuggingFace Hub.

    Examples:
        ttx search              # List popular TTS models
        ttx search "qwen"       # Search for Qwen models
        ttx search --limit 10   # Show only 10 results
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

        # Create table
        table = Table(title=f"Found {len(models)} TTS Models", show_lines=False)
        table.add_column("Model ID", style="cyan", no_wrap=True)
        table.add_column("Downloads", style="green", justify="right")
        table.add_column("Likes", style="yellow", justify="right")
        table.add_column("Modified", style="blue")

        for model in models:
            table.add_row(
                model.model_id,
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
        raise typer.Exit(1)


@app.command()
def install(
    model_id: str = typer.Argument(..., help="Model ID to install (e.g., author/model-name)"),
) -> None:
    """Install a TTS model from HuggingFace Hub.

    Examples:
        ttx install Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
        ttx install OpenMOSS-Team/MOSS-TTS
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
        raise typer.Exit(1)


@app.command()
def models() -> None:
    """List installed TTS models.

    Examples:
        ttx models
    """
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
        raise typer.Exit(1)


@app.command()
def remove(
    model_id: str = typer.Argument(..., help="Model ID to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Remove an installed TTS model.

    Examples:
        ttx remove author/model-name
        ttx remove author/model-name --force
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
        raise typer.Exit(1)


@app.command()
def info(
    model_id: str = typer.Argument(..., help="Model ID"),
) -> None:
    """Show detailed information about a model.

    Examples:
        ttx info author/model-name
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
        raise typer.Exit(1)


@app.callback()
def main() -> None:
    """ttx - Modern CLI for text-to-speech generation and model management."""
    pass


if __name__ == "__main__":
    app()
