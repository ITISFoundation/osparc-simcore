import logging

import typer
from settings_library.cli_utils import create_settings_command

from ._meta import PROJECT_NAME
from .core.settings import AppSettings

log = logging.getLogger(__name__)
main = typer.Typer(name=PROJECT_NAME)


main.command()(create_settings_command(settings_cls=AppSettings, logger=log))


@main.command()
def run():
    """Runs application"""
    typer.secho("Sorry, this entrypoint is intentionally disabled." "Use instead")
    typer.secho(
        "$ uvicorn simcore_service_api_server.main:the_app",
        fg=typer.colors.BLUE,
    )
