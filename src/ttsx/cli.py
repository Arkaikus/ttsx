"""CLI entry point for ttsx.

Each command is defined inside its own commands/*.py module as a
typer.Typer() app. This file only wires them into the top-level app
via add_typer() — no business logic lives here.
"""

import typer

from ttsx.commands import (
    clone_app,
    generate_app,
    hw_app,
    models_app,
    search_app,
    version_app,
    voices_app,
)

app = typer.Typer(
    name="ttsx",
    help="Modern CLI for text-to-speech generation and model management",
    no_args_is_help=True,
)

app.add_typer(hw_app,       name="hw")
app.add_typer(version_app,  name="version")
app.add_typer(search_app,   name="search")
app.add_typer(generate_app, name="generate")
app.add_typer(clone_app,    name="clone")
app.add_typer(voices_app,   name="voices")
app.add_typer(models_app,   name="models")


@app.callback()
def main() -> None:
    """ttsx — Modern CLI for text-to-speech generation and model management."""


if __name__ == "__main__":
    app()
