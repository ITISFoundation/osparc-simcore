# Allows entrypoint via python -m as well

from typing import Optional

import rich
import typer

from . import __version__
from .commands import compose, config, metadata, run_creator

app = typer.Typer()


def version_callback(value: bool):
    if value:
        rich.print(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", callback=version_callback
    ),
):
    """o2s2parc service integration library"""
    assert version or not version  # nosec


# new
app.command("compose")(compose.main)
app.command("config")(config.main)
# legacy
app.command("bump-version")(metadata.bump_version)
app.command("get-version")(metadata.get_version)
app.command("run-creator")(run_creator.main)
