from pathlib import Path

import rich
import typer

from ..service import pytest_runner


def main(
    service_dir: Path = typer.Argument(
        ..., help="Root directory of the service under test"
    ),
):
    """Runs tests against service directory"""

    if not service_dir.exists():
        raise typer.BadParameter("Invalid path to service directory")

    rich.print(f"Testing '{service_dir.resolve()}' ...")
    error_code = pytest_runner.main(service_dir=service_dir, extra_args=[])
    raise typer.Exit(code=error_code)
