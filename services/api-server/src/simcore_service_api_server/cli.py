import logging

import typer
from settings_library.utils_cli import create_settings_command

from ._meta import PROJECT_NAME
from .core.settings import ApplicationSettings

log = logging.getLogger(__name__)
main = typer.Typer(name=PROJECT_NAME)


main.command()(create_settings_command(settings_cls=ApplicationSettings, logger=log))


@main.command()
def run():
    """Runs application"""
    typer.secho("Sorry, this entrypoint is intentionally disabled. Use instead")
    typer.secho(
        "$ uvicorn --factory simcore_service_api_server.main:app_factory",
        fg=typer.colors.BLUE,
    )
