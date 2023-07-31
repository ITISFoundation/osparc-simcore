import logging

import typer
from settings_library.utils_cli import create_settings_command

from ._meta import PROJECT_NAME
from .core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)

# NOTE: 'main' variable is referred in the setup's entrypoint!
main = typer.Typer(name=PROJECT_NAME)

main.command()(
    create_settings_command(settings_cls=ApplicationSettings, logger=_logger)
)


@main.command()
def run():
    """Runs application"""
    typer.secho("Sorry, this entrypoint is intentionally disabled. Use instead")
    typer.secho(
        "$ uvicorn simcore_service_catalog.main:the_app",
        fg=typer.colors.BLUE,
    )
