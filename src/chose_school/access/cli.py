"""Compatibility exports for the CLI access layer.

The executable entry point is ``chose_school.main:main``. Import the parser and
dispatcher from here only when embedding the CLI in another local process.
"""

from chose_school.access.cli_parser import create_parser, parse_arguments
from chose_school.access.command_handlers import dispatch_command

__all__ = ["create_parser", "dispatch_command", "parse_arguments"]
