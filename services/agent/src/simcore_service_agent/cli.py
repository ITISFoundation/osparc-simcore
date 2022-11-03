import logging

import typer
from settings_library.utils_cli import create_settings_command

from ._meta import APP_NAME
from .core.settings import ApplicationSettings

log = logging.getLogger(__name__)

main = typer.Typer(name=APP_NAME)

main.command()(create_settings_command(settings_cls=ApplicationSettings, logger=log))
