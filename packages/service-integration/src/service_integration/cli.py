# Allows entrypoint via python -m as well

from typing import Optional

import rich
import typer

from . import __version__
from .commands import compose, config, metadata, run_creator
from .context import IntegrationContext

DEFAULTS = IntegrationContext()

app = typer.Typer()


def version_callback(value: bool):
    if value:
        rich.print(__version__)
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
    ),
    registry_name: str = typer.Option(
        DEFAULTS.REGISTRY_NAME,
        "--REGISTRY_NAME",
        help="sets docker registry",
    ),
    compose_version: str = typer.Option(
        DEFAULTS.COMPOSE_VERSION,
        "--COMPOSE_VERSION",
        help="sets docker-compose spec version",
    ),
):
    """o2s2parc service integration library"""
    assert version or not version  # nosec
    ctx.integration_context = IntegrationContext(
        REGISTRY_NAME=registry_name,
        COMPOSE_VERSION=compose_version,
    )


# new
app.command("compose")(compose.main)
app.command("config")(config.main)
# legacy
app.command("bump-version")(metadata.bump_version)
app.command("get-version")(metadata.get_version)
app.command("run-creator")(run_creator.main)
