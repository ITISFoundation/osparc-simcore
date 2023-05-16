import getpass
import logging
import random

import rich
import typer
from pydantic import SecretStr
from rich.console import Console
from servicelib.utils_secrets import generate_password
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
):
    """o2s2parc resource usage"""
    assert ctx  # nosec
    assert version or not version  # nosec


#
# COMMANDS
#


@app.command()
def generate_dotenv(ctx: typer.Context, auto_password: bool = False):
    """Generates an example of environment variables file (or dot-envfile)

    Usage sample:

    $ resource-usage-tracker-cli generate-dotenv > .env

    $ cat .env

    $ set -o allexport; source .env; set +o allexport
    """
    assert ctx  # nosec

    username = getpass.getuser()
    password: str = (
        getpass.getpass(prompt="Password [Press Enter to auto-generate]: ")
        if not auto_password
        else None
    ) or generate_password(length=32)

    settings = ApplicationSettings.create_from_envs(
        RESOURCE_USAGE_PROMETHEUS_URL="http://127.0.0.1:8000",
        RESOURCE_USAGE_PROMETHEUS_PORT=random.randint(1024, 65535),
    )

    for name, value in settings.dict().items():
        if name.startswith("RESOURCE_USAGE_"):
            value = (
                f"{value.get_secret_value()}" if isinstance(value, SecretStr) else value
            )
            print(f"{name}={'null' if value is None else value}")


app.command()(create_settings_command(settings_cls=ApplicationSettings, logger=log))


@app.command()
def serve(
    ctx: typer.Context,
    reload: bool = False,
):
    """Starts server with http API"""
    assert ctx  # nosec
    web_server.start(log_level="info", reload=reload)
