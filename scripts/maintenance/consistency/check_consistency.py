#! /usr/bin/env python3

import asyncio
import contextlib
import datetime
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any

import arrow
import sqlalchemy as sa
import typer
from dotenv import dotenv_values
from pydantic import BaseModel, ByteSize, PostgresDsn, field_validator
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
            "POSTGRES_PUBLIC_HOST",
        ]:
            assert state.environment[env]
        postgres_db = PostgresDB(
            dsn=f"postgresql+asyncpg://{state.environment['POSTGRES_USER']}:{state.environment['POSTGRES_PASSWORD']}@{state.environment['POSTGRES_PUBLIC_HOST']}/{state.environment['POSTGRES_DB']}"
        )

        engine = create_async_engine(
            f"{postgres_db.dsn}",
            connect_args={
                "server_settings": {
                    "application_name": "osparc-data-consistency-script"
                }
            },
            pool_size=10,
            max_overflow=30,
        )
        yield engine
    finally:
        if engine:
            await engine.dispose()


def _parse_environment(deploy_config: Path) -> dict[str, str | None]:
    repo_config = deploy_config / "repo.config"
    assert repo_config.exists()
    non_interpolated_environment = dotenv_values(repo_config, interpolate=False)
    if non_interpolated_environment.get("AUTOSCALING_EC2_ACCESS_KEY_ID", "").startswith(
        "${TF_"
    ):
        print(
            "[yellow bold]Terraform variables detected, looking for repo.config.frozen as alternative."
            " TIP: you are responsible for them being up to date!![/yellow bold]"
        )
        repo_config = deploy_config / "repo.config.frozen"
        assert (
            repo_config.exists()
        ), f"{repo_config} is missing, you need to generate it! "
    environment = dotenv_values(repo_config)
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
        print("getting project nodes...")
        result = await conn.execute(
            sa.text(
                "SELECT uuid, workbench, prj_owner, users.name, users.email"
                ' FROM "projects"'
                " INNER JOIN users"
                " ON projects.prj_owner = users.id"
                " WHERE users.role != 'GUEST'"
            )
        )
        project_nodes = {
            project_uuid: {
                "nodes": list(workbench.keys()),
                "owner": prj_owner,
                "name": user_name,
                "email": user_email,
            }
            for project_uuid, workbench, prj_owner, user_name, user_email in result
            if len(workbench) > 0
        }

        print(f"found {len(project_nodes)} project with non empty workbench")

    return project_nodes


@dataclass(frozen=True)
class FileInfo:
    file_id: str
    file_size: ByteSize
    last_modified: datetime.datetime


ProjectID = str
NodeID = str


@dataclass(frozen=True)
class ProjectInfo:
    uuid: ProjectID
    workbench: dict[NodeID, set[FileInfo]]
    owner: int
    name: str
    email: str


async def _get_files_from_project_nodes(
    engine: AsyncEngine, project_uuid: str, node_ids: list[str]
) -> set[FileInfo]:
    async with engine.connect() as conn:
        array = str([f"{project_uuid}/{n}%" for n in node_ids])
        result = await conn.execute(
            sa.text(
                "SELECT file_id, file_size, last_modified"  # noqa: S608
                ' FROM "file_meta_data"'
                f" WHERE file_meta_data.file_id LIKE any (array{array}) AND location_id = '0'"
            )
        )

        # here we got all the files for that project uuid/node_ids combination
        project_nodes_files = {
            FileInfo(
                file_id, file_size, arrow.get(last_modified or "2000-01-01").datetime
            )
            for file_id, file_size, last_modified in result
        }
        return project_nodes_files


async def _get_all_invalid_files_from_file_meta_data(
    engine: AsyncEngine,
) -> set[FileInfo]:
    async with engine.connect() as conn:
        print("getting invalid files from file_meta_data...")
        result = await conn.execute(
            sa.text(
                'SELECT file_id, file_size, last_modified FROM "file_meta_data" '
                "WHERE file_meta_data.file_size < 1 OR file_meta_data.entity_tag IS NULL"
            )
        )
        # here we got all the files for that project uuid/node_ids combination
        invalid_files_in_file_meta_data = {
            FileInfo(
                file_id, file_size, arrow.get(last_modified or "2000-01-01").datetime
            )
            for file_id, file_size, last_modified in result
        }
        print(f"found {len(invalid_files_in_file_meta_data)}")
        return invalid_files_in_file_meta_data


# Set a reasonable limit for concurrent database access
CONNECTION_LIMIT = 30  # Adjust the limit as appropriate


async def limited_gather(*tasks, limit):
    semaphore = asyncio.Semaphore(limit)

    async def sem_task(task):
        async with semaphore:
            return await task

    return await asyncio.gather(*(sem_task(task) for task in tasks))


async def _list_all_invalid_entries_in_file_meta_data(
    engine: AsyncEngine,
) -> set[FileInfo]:
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.text(
                """
SELECT file_id, file_size, last_modified FROM "file_meta_data"
WHERE (file_size < 0 OR entity_tag IS NULL) AND is_directory IS FALSE
"""
            )
        )
        # here we got all the files for that project uuid/node_ids combination
        file_infos = {
            FileInfo(
                file_id, file_size, arrow.get(last_modified or "2000-01-01").datetime
            )
            for file_id, file_size, last_modified in result
        }
        print(f"[yellow bold]found {len(file_infos)} invalid entries in file_meta_data")
        return file_infos


async def _list_all_invalid_soft_links_in_file_meta_data(
    engine: AsyncEngine,
) -> set[FileInfo]:
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.text(
                """
SELECT f1.file_id, f1.file_size, f1.last_modified
FROM file_meta_data AS f1
LEFT JOIN file_meta_data AS f2 ON f1.object_name = f2.file_id
WHERE f1.is_soft_link IS TRUE
AND f2.file_id IS NULL
"""
            )
        )
        file_infos = {
            FileInfo(
                file_id, file_size, arrow.get(last_modified or "2000-01-01").datetime
            )
            for file_id, file_size, last_modified in result
        }
        print(f"[yellow bold]found {len(file_infos)} invalid entries in file_meta_data")
        return file_infos


async def _list_unused_file_meta_data_entries(engine: AsyncEngine) -> set[FileInfo]:
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.text(
                """
SELECT f1.file_id, f1.file_size, f1.last_modified
FROM file_meta_data AS f1
LEFT JOIN file_meta_data AS f2 ON f1.object_name = f2.file_id
WHERE f1.is_soft_link IS TRUE
AND f2.file_id IS NULL
"""
            )
        )
        file_infos = {
            FileInfo(
                file_id, file_size, arrow.get(last_modified or "2000-01-01").datetime
            )
            for file_id, file_size, last_modified in result
        }
        print(f"[yellow bold]found {len(file_infos)} invalid entries in file_meta_data")
        return file_infos


async def _summary() -> None:
    # ---------------------- GET FILE ENTRIES FROM DB PROKECT TABLE -------------------------------------------------------------
    async with db_engine() as engine:
        invalid_file_infos = await _list_all_invalid_entries_in_file_meta_data(engine)
        invalid_soft_links = await _list_all_invalid_soft_links_in_file_meta_data(
            engine
        )
        unused_file_entries = await _list_unused_file_meta_data_entries(engine)

    print("[yellow bold]Very good we are done!")


@app.command()
def summary() -> None:
    """Show a summary of the current status of data consistency (S3 vs file_meta_data table).

    Arguments:
        repo_config -- path that shall point to a repo.config type of file (see osparc-ops-deployment-configuration repository)

    """

    asyncio.run(_summary())


if __name__ == "__main__":
    app()
