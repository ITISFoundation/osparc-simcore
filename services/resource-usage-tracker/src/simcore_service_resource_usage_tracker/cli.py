import logging
from typing import Any

import rich
import typer
from pydantic import AnyUrl, SecretStr, parse_obj_as
from rich.console import Console
from settings_library.postgres import PostgresSettings
from settings_library.prometheus import PrometheusSettings
from settings_library.utils_cli import create_settings_command

from . import web_server
from ._meta import PROJECT_NAME, __version__
from .core.settings import ApplicationSettings

# SEE setup entrypoint 'simcore_service_invitations.cli:app'
app = typer.Typer(name=PROJECT_NAME)
log = logging.getLogger(__name__)

err_console = Console(stderr=True)


def _version_callback(value: bool):
    if value:
        rich.print(__version__)
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: bool
    | None = (
        typer.Option(
            None,
            "--version",
            callback=_version_callback,
            is_eager=True,
        )
    ),
) -> None:
    """o2s2parc resource usage tracker"""
    assert ctx  # nosec
    assert version or not version  # nosec


#
# COMMANDS
#


@app.command()
def generate_dotenv(ctx: typer.Context) -> None:
    """Generates an example of environment variables file (or dot-envfile)

    Usage sample:

    $ resource-usage-tracker-cli generate-dotenv > .env

    $ cat .env

    $ set -o allexport; source .env; set +o allexport
    """
    assert ctx  # nosec

    settings = ApplicationSettings(
        RESOURCE_USAGE_TRACKER_PROMETHEUS=PrometheusSettings(
            PROMETHEUS_URL=parse_obj_as(AnyUrl, "http://prometheus:9090"),
            PROMETHEUS_USERNAME="my-username",
            PROMETHEUS_PASSWORD=SecretStr("my-password"),
        ),
        RESOURCE_USAGE_TRACKER_POSTGRES=PostgresSettings(
            POSTGRES_HOST="postgres",
            POSTGRES_USER="postgres_user",
            POSTGRES_PASSWORD=SecretStr("postgres-password"),
            POSTGRES_DB="osparc",
        ),
    )

    def _resolve_settings(settings_dict: dict[str, Any]) -> dict[str, Any]:
        resolved_settings = {}
        for name, value in settings_dict.items():
            if isinstance(value, dict):
                resolved_settings[name] = _resolve_settings(value)
            elif isinstance(value, SecretStr):
                resolved_settings[name] = value.get_secret_value()
            else:
                resolved_settings[name] = f"{value}"
        return resolved_settings

    resolved_settings = _resolve_settings(settings.dict())
    for name, value in resolved_settings.items():
        if name.startswith("RESOURCE_USAGE_TRACKER_"):
            print(f"{name}={'null' if value is None else value}")


app.command()(create_settings_command(settings_cls=ApplicationSettings, logger=log))


@app.command()
def serve(
    ctx: typer.Context,
    reload: bool = False,
) -> None:
    """Starts server with http API"""
    assert ctx  # nosec
    web_server.start(log_level="info", reload=reload)
