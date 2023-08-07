import asyncio
import logging
from typing import Annotated, Any

import rich
import typer
from models_library.users import UserID
from rich.console import Console
from settings_library.utils_cli import create_settings_command
from simcore_service_resource_usage_tracker.core.errors import ConfigurationError
from simcore_service_resource_usage_tracker.modules.prometheus import create_client
from simcore_service_resource_usage_tracker.modules.prometheus_containers.cli_placeholder import (
    collect_and_return_service_resource_usage,
)

from ._meta import PROJECT_NAME, __version__
from .core.settings import ApplicationSettings, MinimalApplicationSettings

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


async def _get_resources(
    settings: MinimalApplicationSettings, user_id: UserID
) -> dict[str, Any]:
    assert settings.RESOURCE_USAGE_TRACKER_PROMETHEUS  # nosec
    prometheus_client = await create_client(settings.RESOURCE_USAGE_TRACKER_PROMETHEUS)
    return await collect_and_return_service_resource_usage(prometheus_client, user_id)


@app.command()
def evaluate(ctx: typer.Context, user_id: int) -> None:
    """Evaluates resources and does blahblahb TBD @mrnicegyu11"""
    assert ctx  # nosec
    settings = MinimalApplicationSettings.create_from_envs()
    err_console.print(
        f"[yellow]running with configuration:\n{settings.json()}[/yellow]"
    )
    if not settings.RESOURCE_USAGE_TRACKER_PROMETHEUS:
        raise ConfigurationError(msg="no valid prometheus endpoint defined!")

    data = asyncio.run(_get_resources(settings, user_id))
    err_console.print(f"received data from prometheus:\n{data}")
