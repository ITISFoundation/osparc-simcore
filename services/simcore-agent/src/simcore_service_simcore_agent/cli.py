import logging

import typer

from ._meta import APP_NAME

log = logging.getLogger(__name__)


main = typer.Typer(name=APP_NAME)


@main.command()
def run():
    """Runs application"""
    typer.secho("Sorry, this entrypoint is intentionally disabled. Use instead")
    typer.secho(
        "$ uvicorn simcore_service_simcore_agent.main:the_app",
        fg=typer.colors.BLUE,
    )
