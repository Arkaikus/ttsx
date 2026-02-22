"""CLI command sub-apps. Each module owns its own typer.Typer() instance."""

from ttsx.commands.clone import app as clone_app
from ttsx.commands.generate import app as generate_app
from ttsx.commands.hardware import app as hw_app
from ttsx.commands.models import app as models_app
from ttsx.commands.search import app as search_app
from ttsx.commands.version import app as version_app
from ttsx.commands.voices import app as voices_app

__all__ = [
    "clone_app",
    "generate_app",
    "hw_app",
    "models_app",
    "search_app",
    "version_app",
    "voices_app",
]
