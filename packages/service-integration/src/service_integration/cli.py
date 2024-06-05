# Allows entrypoint via python -m as well

from typing import Annotated

import rich
import typer

from ._meta import __version__
from .commands import compose, metadata, run_creator, test
from .commands.config import config_app
from .settings import AppSettings

app = typer.Typer()


def _version_callback(value: bool):  # noqa: FBT002
    if value:
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
    ] = None,
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


app.command("compose")(compose.create_compose)
app.add_typer(config_app, name="config")
app.command("test")(test.run_tests)


# legacy

app.command("bump-version")(metadata.bump_version)
app.command("get-version")(metadata.get_version)
app.command("run-creator")(run_creator.main)

# Display help message for compose as an alias
@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo("Use --help for more information on specific commands.")
