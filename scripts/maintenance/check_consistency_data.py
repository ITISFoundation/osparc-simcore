#! /usr/bin/env python3

"""Script to check consistency of the file storage backend in oSparc.



    1. From an osparc database, go over all projects, get the project IDs and Node IDs
    2. From the same database, now get all the files listed like projectID/nodeID from 1.
    3. We get a list of files that are needed for the current projects
    4. connect to the S3 backend, check that these files exist
    5. generate a report with: project uuid, owner, files missing in S3
"""
import asyncio
import logging
import os
import re
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Set

import aiopg
import typer
from tenacity import after_log, retry, stop_after_attempt, wait_random

log = logging.getLogger(__name__)


@asynccontextmanager
async def managed_docker_compose(
    postgres_volume_name: str, postgres_username: str, postgres_password: str
):
    typer.echo(f"starting up database in localhost")
    compose_file = Path.cwd() / "consistency" / "docker-compose.yml"
    try:
        subprocess.run(
            f"docker-compose --file {compose_file} up --detach",
            shell=True,
            check=True,
            cwd=compose_file.parent,
            env={**os.environ, **{"POSTGRES_DATA_VOLUME": postgres_volume_name}},
        )
        typer.echo(
            f"database started: adminer available on http://127.0.0.1:18080/?pgsql=postgres&username={postgres_username}&db=simcoredb&ns=public"
        )

        @retry(
            wait=wait_random(1, 3),
            stop=stop_after_attempt(10),
            after=after_log(log, logging.WARN),
        )
        async def postgres_responsive():
            async with aiopg.create_pool(
                f"dbname=simcoredb user={postgres_username} password={postgres_password} host=127.0.0.1"
            ) as pool:
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT 1")

        await postgres_responsive()
        yield
    finally:
        subprocess.run(
            f"docker-compose --file {compose_file} down",
            shell=True,
            check=True,
            cwd=compose_file.parent,
        )


async def _get_projects_nodes(pool) -> Dict[str, List[str]]:
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT uuid, workbench"
                ' FROM "projects"'
                " INNER JOIN users"
                " ON projects.prj_owner = users.id"
                " WHERE users.role != 'GUEST'"
            )
            typer.secho(
                f"found {cursor.rowcount} projects, now getting project/node ids..."
            )
            project_db_rows = await cursor.fetchall()
        project_nodes = {
            project_uuid: list(workbench.keys())
            for project_uuid, workbench in project_db_rows
            if workbench
        }
        typer.echo(
            f"processed {cursor.rowcount} projects, now looking for files in the file_meta_data table..."
        )
        return project_nodes


async def _get_files_from_project_nodes(
    pool, project_uuid: str, node_ids: List[str]
) -> Set[str]:
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            array = str([f"{project_uuid}/{n}%" for n in node_ids])
            await cursor.execute(
                "SELECT file_uuid"
                ' FROM "file_meta_data"'
                f" WHERE file_meta_data.file_uuid LIKE any (array{array}) AND location_id = '0'"
            )

            # here we got all the files for that project uuid/node_ids combination
            file_rows = await cursor.fetchall()
            return {file[0] for file in file_rows}


async def _get_files_from_s3_backend(
    s3_endpoint: str,
    s3_access: str,
    s3_secret: str,
    s3_bucket: str,
    project_uuid: str,
    progress,
) -> Set[str]:
    s3_file_entries = set()
    try:
        completed_process = subprocess.run(
            f"docker run "
            f"--env MC_HOST_mys3='https://{s3_access}:{s3_secret}@{s3_endpoint}' "
            "minio/mc "
            f"ls --recursive mys3/{s3_bucket}/{project_uuid}/",
            shell=True,
            check=True,
            capture_output=True,
        )
        if completed_process.stdout != b"":
            # formatted as:
            # [2021-09-07 04:35:49 UTC] 1.5GiB 05e821d1-2b4b-455f-86b6-9e197545c1ad/work.tgz
            # DATE_creation? size node_id/file_path.ext
            list_of_files = completed_process.stdout.decode("UTF-8").split("\n")
            for file in list_of_files:
                match = re.findall(r".* (.+)", file)
                if match:
                    s3_file_entries.add(f"{project_uuid}/{match[0]}")

    except subprocess.CalledProcessError:
        pass
    progress.update(1)
    return s3_file_entries


async def main_async(
    postgres_volume_name: str,
    postgres_username: str,
    postgres_password: str,
    s3_endpoint: str,
    s3_access: str,
    s3_secret: str,
    s3_bucket: str,
):

    async with managed_docker_compose(
        postgres_volume_name, postgres_username, postgres_password
    ):
        # now the database is up, let's get all the projects owned by a non-GUEST account
        async with aiopg.create_pool(
            f"dbname=simcoredb user={postgres_username} password={postgres_password} host=127.0.0.1"
        ) as pool:
            project_nodes = await _get_projects_nodes(pool)
            # Rationale: the project database does not contain all the files in a node (logs, state files are missing)
            # Therefore, we will list here all the files that are registered in the file_meta_data table using the same projectid/nodeid
            all_sets_of_file_entries = await asyncio.gather(
                *[
                    _get_files_from_project_nodes(pool, project_uuid, node_ids)
                    for project_uuid, node_ids in project_nodes.items()
                ]
            )
    db_file_entries = set().union(*all_sets_of_file_entries)
    db_file_entries_path = Path.cwd() / "project_file_entries.txt"
    db_file_entries_path.write_text("\n".join(db_file_entries))
    typer.secho(
        f"processed {len(project_nodes)} projects, found {len(db_file_entries)} file entries, saved in {db_file_entries_path}",
        fg=typer.colors.YELLOW,
    )

    # let's proceed with S3 backend: files are saved in BUCKET_NAME/projectID/nodeID/fileA.ext
    # Rationale: Similarly we list here all the files in each of the projects. And it goes faster to list them recursively.
    typer.echo(
        f"now connecting with S3 backend and getting files for {len(project_nodes)} projects..."
    )
    with typer.progressbar(length=len(project_nodes)) as progress:
        all_sets_in_s3 = await asyncio.gather(
            *[
                _get_files_from_s3_backend(
                    s3_endpoint, s3_access, s3_secret, s3_bucket, project_uuid, progress
                )
                for project_uuid in project_nodes
            ]
        )
    s3_file_entries = set().union(*all_sets_in_s3)
    s3_file_entries_path = Path.cwd() / "s3_file_entries.txt"
    s3_file_entries_path.write_text("\n".join(s3_file_entries))
    typer.echo(
        f"processed {len(project_nodes)} projects, found {len(s3_file_entries)} file entries, saved in {s3_file_entries_path}"
    )

    typer.echo(
        f"Refining differences between DB:{len(db_file_entries)} files and S3:{len(s3_file_entries)} files..."
    )

    common_files = db_file_entries.intersection(s3_file_entries)
    s3_missing_files = db_file_entries.difference(s3_file_entries)
    db_missing_files = s3_file_entries.difference(db_file_entries)

    typer.secho(
        f"{len(common_files)} files are the same in both system", fg=typer.colors.BLUE
    )
    typer.secho(
        f"{len(s3_missing_files)} files are the missing in S3", fg=typer.colors.RED
    )
    typer.secho(
        f"{len(db_missing_files)} files are the missing in DB", fg=typer.colors.RED
    )


def main(
    postgres_volume_name: str,
    postgres_username: str,
    postgres_password: str,
    s3_endpoint: str,
    s3_access: str,
    s3_secret: str,
    s3_bucket: str,
):
    asyncio.run(
        main_async(
            postgres_volume_name,
            postgres_username,
            postgres_password,
            s3_endpoint,
            s3_access,
            s3_secret,
            s3_bucket,
        )
    )


if __name__ == "__main__":
    typer.run(main)
