"""Version command."""

from rich.console import Console

console = Console()


def version_command() -> None:
    """Show ttsx version."""
    from ttsx import __version__

    console.print(f"ttsx version [bold]{__version__}[/bold]")
