"""Version command."""

import typer
from rich.console import Console

app = typer.Typer(help="Show ttsx version.")
console = Console()


@app.callback(invoke_without_command=True)
def version() -> None:
    """Show ttsx version."""
    from ttsx import __version__

    console.print(f"ttsx version [bold]{__version__}[/bold]")
