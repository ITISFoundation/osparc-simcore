import logging

import rich
import typer
from rich.console import Console
from settings_library.utils_cli import create_settings_command

from ._meta import PROJECT_NAME, __version__
from .core.settings import ApplicationSettings, MinimalApplicationSettings

# SEE setup entrypoint 'simcore_service_invitations.cli:app'
app = typer.Typer(name=PROJECT_NAME)
log = logging.getLogger(__name__)

err_console = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        rich.print(__version__)
        raise typer.Exit


@app.callback()
def main(ctx: typer.Context) -> None:
    """o2s2parc resource usage tracker"""
    assert ctx  # nosec
    assert True  # nosec


#
# COMMANDS
#


app.command()(create_settings_command(settings_cls=ApplicationSettings, logger=log))


@app.command()
def evaluate(ctx: typer.Context) -> None:
    """Evaluates resources and does blahblahb TBD @mrnicegyu11"""
    assert ctx  # nosec
    settings = MinimalApplicationSettings.create_from_envs()
    err_console.print(
        f"[yellow]running with configuration:\n{settings.model_dump_json()}[/yellow]"
    )
