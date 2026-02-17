"""Hardware detection command."""

import json
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ttsx.hardware import HardwareDetector

console = Console()


def hw_command(json_output: bool = False, verbose: bool = False) -> None:
    """Display hardware information and TTS capabilities.

    Args:
        json_output: Output as JSON instead of formatted tables.
        verbose: Show additional detailed information.
    """
    detector = HardwareDetector()
    info = detector.detect()

    if json_output:
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

    # Single unified table for all hardware info
    table = Table(
        title="Hardware Information",
        show_header=False,
        title_style="bold cyan",
        expand=True,
        box=None,
        padding=(0, 1),
    )
    table.add_column("Category", style="cyan", width=12)
    table.add_column("Property", style="blue", width=18)
    table.add_column("Value", style="white", no_wrap=False, overflow="fold")

    # Compute section
    if info.cuda_available:
        table.add_row("Compute", "Device", "[bold green]CUDA GPU[/bold green]")
        for i, gpu in enumerate(info.gpus):
            prefix = "Compute" if i == 0 else ""
            table.add_row(prefix, "GPU Model", gpu.name)
            if len(info.gpus) > 1:
                table.add_row("", "GPU Index", str(gpu.index))
            table.add_row(
                "",
                "VRAM",
                f"{gpu.memory.total_gb:.1f} GB total / "
                f"[bold green]{gpu.memory.available_gb:.1f} GB[/bold green] available",
            )
            if verbose and gpu.memory.used_gb > 0:
                table.add_row("", "VRAM Used", f"{gpu.memory.used_gb:.1f} GB")
            if gpu.compute_capability:
                table.add_row(
                    "",
                    "Compute Capability",
                    f"{gpu.compute_capability[0]}.{gpu.compute_capability[1]}",
                )
        table.add_row("", "CUDA Version", info.cuda_version or "N/A")
    elif info.mps_available:
        table.add_row("Compute", "Device", "[bold green]Apple Metal (MPS)[/bold green]")
        table.add_row("", "Acceleration", "GPU via Metal")
    else:
        table.add_row("Compute", "Device", "[bold yellow]CPU only[/bold yellow]")
        table.add_row("", "⚠ Note", "[yellow]No GPU detected[/yellow]")

    # CPU section
    table.add_row("CPU", "Model", info.cpu_model)
    table.add_row("", "Cores", f"{info.cpu_cores} physical / {info.cpu_threads} logical")
    table.add_row(
        "",
        "RAM",
        f"{info.ram_total_gb:.1f} GB total / "
        f"[bold green]{info.ram_available_gb:.1f} GB[/bold green] available",
    )

    # Software section
    table.add_row("Software", "PyTorch", info.pytorch_version)
    if info.pytorch_cuda_version:
        table.add_row("", "Build", f"CUDA {info.pytorch_cuda_version}")
    else:
        table.add_row("", "Build", "CPU")
    table.add_row("", "Default Device", f"[bold]{info.device_type}[/bold]")

    # Display table
    console.print()
    console.print(table)

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
