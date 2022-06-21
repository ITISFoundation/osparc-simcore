import logging

import typer
from settings_library.utils_cli import create_settings_command

from ._meta import PROJECT_NAME
from .core.settings import DynamicSidecarSettings

log = logging.getLogger(__name__)
main = typer.Typer(name=PROJECT_NAME)


main.command()(create_settings_command(settings_cls=DynamicSidecarSettings, logger=log))


@main.command()
def run():
    """Runs application"""
    typer.secho("Sorry, this entrypoint is intentionally disabled." "Use instead")
    typer.secho(
        "$ uvicorn simcore_service_dynamic_sidecar.main:app",
        fg=typer.colors.BLUE,
    )
