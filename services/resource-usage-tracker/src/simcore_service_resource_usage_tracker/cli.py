import logging
from typing import Annotated

import rich
import typer
from rich.console import Console
from settings_library.utils_cli import create_settings_command

from . import web_server
from ._meta import PROJECT_NAME, __version__
from .core.settings import ApplicationSettings

# SEE setup entrypoint 'simcore_service_invitations.cli:app'
app = typer.Typer(name=PROJECT_NAME)
log = logging.getLogger(__name__)

err_console = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        rich.print(__version__)
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """o2s2parc resource usage tracker"""
    assert ctx  # nosec
    assert version or not version  # nosec


#
# COMMANDS
#


app.command()(create_settings_command(settings_cls=ApplicationSettings, logger=log))


@app.command()
def serve(
    ctx: typer.Context,
    reload: bool = False,
) -> None:
    """Starts server with http API"""
    assert ctx  # nosec
    web_server.start(log_level="info", reload=reload)
