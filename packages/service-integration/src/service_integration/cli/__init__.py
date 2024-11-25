# Allows entrypoint via python -m as well

from typing import Annotated

import rich
import typer

from .._meta import __version__
from ..settings import AppSettings
from . import _compose_spec, _metadata, _run_creator, _test
from ._config import config_app

app = typer.Typer()


def _version_callback(value: bool) -> None:  # noqa: FBT001
    if value:
        rich.print(__version__)
        raise typer.Exit


@app.callback()
def main(
    ctx: typer.Context,
    registry_name: (
        Annotated[
            str,
            typer.Option(
                "--REGISTRY_NAME",
                help="image registry name. Full url or prefix used as prefix in an image name",
            ),
        ]
        | None
    ) = None,
    compose_version: (
        Annotated[
            str,
            typer.Option(
                "--COMPOSE_VERSION",
                help="version used for docker compose specification",
            ),
        ]
        | None
    ) = None,
    version: Annotated[  # noqa: FBT002
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
):
    """o2s2parc service Integration Library (OOIL in short)"""
    assert isinstance(version, bool | None)  # nosec

    overrides = {}
    if registry_name:
        overrides["REGISTRY_NAME"] = registry_name

    if compose_version:
        overrides["COMPOSE_VERSION"] = compose_version

    # save states
    ctx.settings = AppSettings.model_validate(overrides)  # type: ignore[attr-defined] # pylint:disable=no-member


#
# REGISTER commands and/or sub-apps
#

app.command("compose")(_compose_spec.create_compose)
app.add_typer(config_app, name="config", help="Manage osparc config files")
app.command("test")(_test.run_tests)
# legacy
app.command("bump-version")(_metadata.bump_version)
app.command("get-version")(_metadata.get_version)
app.command("run-creator")(_run_creator.run_creator)
