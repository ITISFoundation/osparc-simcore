import logging

import typer
from settings_library.utils_cli import create_settings_command

from ._app import Application
from ._main import create_application
from ._meta import APP_NAME
from ._settings import ApplicationSettings
from .info import request_info

log = logging.getLogger(__name__)

main = typer.Typer(name=APP_NAME)

main.command()(create_settings_command(settings_cls=ApplicationSettings, logger=log))


@main.command()
def run():
    """Runs application"""
    app: Application = create_application()
    app.run()


@main.command()
def info():
    """Prints information about the status of a local running agent"""
    typer.echo(request_info())
