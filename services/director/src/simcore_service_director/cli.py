import logging

import typer
from settings_library.utils_cli import create_settings_command, create_version_callback

from ._meta import PROJECT_NAME, __version__
from .core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)

main = typer.Typer(name=PROJECT_NAME)

main.command()(
    create_settings_command(settings_cls=ApplicationSettings, logger=_logger)
)
main.callback()(create_version_callback(__version__))


@main.command()
def run():
    """Runs application"""
    typer.secho("Sorry, this entrypoint is intentionally disabled. Use instead")
    typer.secho(
        "$ uvicorn simcore_service_director.main:the_app",
        fg=typer.colors.BLUE,
    )
