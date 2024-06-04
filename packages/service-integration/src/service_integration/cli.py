# Allows entrypoint via python -m as well

from typing import Annotated

import rich
import typer

from ._meta import __version__
from .commands import compose, config, metadata, run_creator, test
from .settings import AppSettings

app = typer.Typer()


def _version_callback(enabled):
    if enabled:
        rich.print(__version__)
        raise typer.Exit


@app.callback()
def main(
    ctx: typer.Context,
    registry_name: Annotated[
        str,
        typer.Option(
            "--REGISTRY_NAME",
            help="image registry name. Full url or prefix used as prefix in an image name",
        ),
    ],
    compose_version: Annotated[
        str,
        typer.Option(
            "--COMPOSE_VERSION",
            help="version used for docker compose specification",
        ),
    ] = None,
    version: Annotated[  # noqa: FBT002
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
):
    """o2s2parc service integration library"""
    assert isinstance(version, bool | None)  # nosec

    overrides = {}
    if registry_name:
        overrides["REGISTRY_NAME"] = registry_name

    if compose_version:
        overrides["COMPOSE_VERSION"] = compose_version

    # save states
    ctx.settings = AppSettings.parse_obj(overrides)


# new
app.command("compose")(compose.main)
app.command("config")(config.main)
app.command("test")(test.main)
# legacy
app.command("bump-version")(metadata.bump_version)
app.command("get-version")(metadata.get_version)
app.command("run-creator")(run_creator.main)
