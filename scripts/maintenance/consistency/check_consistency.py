#! /usr/bin/env python3

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any

import sqlalchemy as sa
import typer
from dotenv import dotenv_values
from pydantic import BaseModel, PostgresDsn, field_validator
from rich import print  # pylint: disable=redefined-builtin
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


class PostgresDB(BaseModel):
    dsn: PostgresDsn

    @classmethod
    @field_validator("db")
    def check_db_name(cls, v):
        assert v.path and len(v.path) > 1, "database must be provided"  # noqa: PT018
        return v


@dataclass(kw_only=True)
class AppState:
    environment: dict[str, str | None] = field(default_factory=dict)
    deploy_config: Path | None = None


app = typer.Typer()
state: AppState = AppState()


@contextlib.asynccontextmanager
async def db_engine() -> AsyncGenerator[AsyncEngine, Any]:
    engine = None
    try:
        for env in [
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_ENDPOINT",
            "POSTGRES_DB",
        ]:
            assert state.environment[env]
        postgres_db = PostgresDB(
            dsn=f"postgresql+asyncpg://{state.environment['POSTGRES_USER']}:{state.environment['POSTGRES_PASSWORD']}@{state.environment['POSTGRES_ENDPOINT']}/{state.environment['POSTGRES_DB']}"
        )

        engine = create_async_engine(
            f"{postgres_db.dsn}",
            connect_args={
                "server_settings": {
                    "application_name": "osparc-data-consistency-script"
                }
            },
        )
        yield engine
    finally:
        if engine:
            await engine.dispose()


def _parse_environment(deploy_config: Path) -> dict[str, str | None]:
    repo_config = deploy_config / "repo.config"
    assert repo_config.exists()
    environment = dotenv_values(repo_config)
    if environment["AUTOSCALING_EC2_ACCESS_KEY_ID"] == "":
        print(
            "Terraform variables detected, looking for repo.config.frozen as alternative."
            " TIP: you are responsible for them being up to date!!"
        )
        repo_config = deploy_config / "repo.config.frozen"
        assert repo_config.exists()
        environment = dotenv_values(repo_config)

        if environment["AUTOSCALING_EC2_ACCESS_KEY_ID"] == "":
            error_msg = (
                "Terraform is necessary in order to check into that deployment!\n"
                f"install terraform (check README.md in {state.deploy_config} for instructions)"
                "then run make repo.config.frozen, then re-run this code"
            )
            print(error_msg)
            raise typer.Abort(error_msg)
    assert environment  # nosec
    return environment


@app.callback()
def main(
    deploy_config: Annotated[
        Path, typer.Option(help="path to the deploy configuration")
    ]
) -> None:
    state.deploy_config = deploy_config.expanduser()
    assert (
        deploy_config.is_dir()
    ), "deploy-config argument is not pointing to a directory!"

    state.environment = _parse_environment(deploy_config)
    assert state.environment


async def _get_projects_nodes(engine: AsyncEngine) -> dict[str, Any]:
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.text(
                "SELECT uuid, workbench, prj_owner, users.name, users.email"
                ' FROM "projects"'
                " INNER JOIN users"
                " ON projects.prj_owner = users.id"
                " WHERE users.role != 'GUEST'"
            )
        )
        all_rows = result.all()
        print(
            f"found {len(all_rows)} project rows, now getting project with valid node ids..."
        )

    project_nodes = {
        project_uuid: {
            "nodes": list(workbench.keys()),
            "owner": prj_owner,
            "name": user_name,
            "email": user_email,
        }
        for project_uuid, workbench, prj_owner, user_name, user_email in all_rows
        if len(workbench) > 0
    }
    print(
        f"processed {len(all_rows)} project rows, found {len(project_nodes)} non-empty projects."
    )
    return project_nodes


async def _summary() -> None:
    async with db_engine() as engine:
        project_nodes = await _get_projects_nodes(engine)

    print("Very good we are done!")


@app.command()
def summary() -> None:
    """Show a summary of the current status of data consistency (S3 vs file_meta_data table).

    Arguments:
        repo_config -- path that shall point to a repo.config type of file (see osparc-ops-deployment-configuration repository)

    """

    asyncio.run(_summary())


if __name__ == "__main__":
    app()
