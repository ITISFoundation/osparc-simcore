import logging

import typer
from settings_library.utils_cli import create_settings_command, create_version_callback

from ._meta import APP_NAME, __version__
from .core.settings import ApplicationSettings

log = logging.getLogger(__name__)

main = typer.Typer(name=APP_NAME)

main.command()(create_settings_command(settings_cls=ApplicationSettings, logger=log))
main.callback()(create_version_callback(__version__))
