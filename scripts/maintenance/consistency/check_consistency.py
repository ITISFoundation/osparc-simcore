#! /usr/bin/env python3

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

import typer
from dotenv import dotenv_values
from rich import print  # pylint: disable=redefined-builtin


@dataclass(kw_only=True)
class AppState:
    environment: dict[str, str | None] = field(default_factory=dict)
    deploy_config: Path | None = None


app = typer.Typer()
state: AppState = AppState()


def _parse_environment(deploy_config: Path) -> dict[str, str | None]:
    repo_config = deploy_config / "repo.config"
    assert repo_config.exists()
    environment = dotenv_values(repo_config)
    assert environment  # nosec
    return environment


@app.callback()
def main(
    deploy_config: Annotated[
        Path, typer.Option(help="path to the deploy configuration")
    ]
):
    state.deploy_config = deploy_config.expanduser()
    assert (
        deploy_config.is_dir()
    ), "deploy-config argument is not pointing to a directory!"

    state.environment = _parse_environment(deploy_config)


async def _summary() -> None:
    print("Very good we are done!")


@app.command()
def summary() -> None:
    """Show a summary of the current status of data consistency (S3 vs file_meta_data table).

    Arguments:
        repo_config -- path that shall point to a repo.config type of file (see osparc-ops-deployment-configuration repository)

    """

    asyncio.run(_summary())
