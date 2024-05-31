# Allows entrypoint via python -m as well


import rich
import typer

from ._meta import __version__
from .commands import compose, config, metadata, run_creator, test
from .settings import AppSettings

app = typer.Typer()


def _version_callback(value: bool):
    if value:
        rich.print(__version__)
        raise typer.Exit


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
    ),
    registry_name: str = typer.Option(
        None,
        "--REGISTRY_NAME",
        help="image registry name. Full url or prefix used as prefix in an image name",
    ),
    compose_version: str = typer.Option(
        None,
        "--COMPOSE_VERSION",
        help="version used for docker compose specification",
    ),
):
    """o2s2parc service integration library"""
    assert True  # nosec

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
