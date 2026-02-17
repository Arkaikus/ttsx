"""CLI command implementations."""

from ttsx.commands.generate import generate_command, voices_command
from ttsx.commands.hardware import hw_command
from ttsx.commands.models import info_command, install_command, models_command, remove_command
from ttsx.commands.search import search_command
from ttsx.commands.version import version_command

__all__ = [
    "generate_command",
    "voices_command",
    "hw_command",
    "search_command",
    "install_command",
    "models_command",
    "remove_command",
    "info_command",
    "version_command",
]
