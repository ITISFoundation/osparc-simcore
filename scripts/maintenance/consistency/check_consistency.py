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
        return {
            FileInfo(
                file_id, file_size, arrow.get(last_modified or "2000-01-01").datetime
            )
            for file_id, file_size, last_modified in result
        }


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
        return {
            FileInfo(
                file_id, file_size, arrow.get(last_modified or "2000-01-01").datetime
            )
            for file_id, file_size, last_modified in result
        }


async def _list_unused_file_meta_data_entries(engine: AsyncEngine) -> set[FileInfo]:
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.text(
                """
SELECT f.file_id, f.file_size, f.last_modified
FROM file_meta_data AS f
LEFT JOIN projects AS p ON f.project_id = p.uuid
WHERE f.project_id IS NOT NULL AND (
    p.uuid IS NULL OR
    NOT (p.workbench->f.node_id) IS NOT NULL
);
"""
            )
        )
        return {
            FileInfo(
                file_id, file_size, arrow.get(last_modified or "2000-01-01").datetime
            )
            for file_id, file_size, last_modified in result
        }


async def _list_unused_api_files(engine: AsyncEngine) -> set[FileInfo]:
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.text(
                """
SELECT fmd.*
FROM file_meta_data fmd
WHERE fmd.project_id IS NULL
AND NOT EXISTS (
    SELECT 1
    FROM projects p
    WHERE CAST(p.workbench AS text) LIKE '%' || REPLACE(fmd.object_name, '_', '\_') || '%'
);
"""
            )
        )
        return {
            FileInfo(
                file_id, file_size, arrow.get(last_modified or "2000-01-01").datetime
            )
            for file_id, file_size, last_modified in result
        }


async def _summary() -> None:
    # ---------------------- GET FILE ENTRIES FROM DB PROKECT TABLE -------------------------------------------------------------
    async with db_engine() as engine:
        invalid_file_infos = await _list_all_invalid_entries_in_file_meta_data(engine)
        print(
            f"[yellow bold]found {len(invalid_file_infos)} invalid entries in file_meta_data"
        )
        invalid_soft_links = await _list_all_invalid_soft_links_in_file_meta_data(
            engine
        )
        print(
            f"[yellow bold]found {len(invalid_soft_links)} invalid soft links in file_meta_data"
        )
        file_entries_with_no_project = await _list_unused_file_meta_data_entries(engine)
        print(
            f"[white]found {len(file_entries_with_no_project)} entries with missing projectID/nodeID in file_meta_data. Do not do anything with this"
        )
        unused_api_files = await _list_unused_api_files(engine)
        print(f"[yellow]found {len(unused_api_files)} unused api files")

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
