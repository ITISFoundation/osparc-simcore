from pathlib import Path
from typing import Annotated

import rich
import typer

from ..service import pytest_runner

test_app = typer.Typer()


@test_app.command("run")
def run_tests(
    service_dir: Annotated[
        Path, typer.Argument(help="Root directory of the service under test")
    ],
):
    """Runs tests against service directory"""

    if not service_dir.exists():
        msg = "Invalid path to service directory"
        raise typer.BadParameter(msg)

    rich.print(f"Testing '{service_dir.resolve()}' ...")
    error_code = pytest_runner.main(service_dir=service_dir, extra_args=[])
    raise typer.Exit(code=error_code)
