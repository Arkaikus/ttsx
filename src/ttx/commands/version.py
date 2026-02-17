"""Version command."""

from rich.console import Console

console = Console()


def version_command() -> None:
    """Show ttx version."""
    from ttx import __version__

    console.print(f"ttx version [bold]{__version__}[/bold]")
