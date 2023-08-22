#! /usr/bin/env python3


import asyncio
import csv
import logging
import os
import re
import subprocess
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import aiopg
import typer
from dateutil import parser
from tenacity import retry
from tenacity.after import after_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_random

log = logging.getLogger(__name__)


@asynccontextmanager
async def managed_docker_compose(
    postgres_volume_name: str, postgres_username: str, postgres_password: str
):
    typer.echo("starting up database in localhost")
    compose_file = Path.cwd() / "consistency" / "docker-compose.yml"
    try:
        subprocess.run(
            ["docker compose", "--file", compose_file, "up", "--detach"],
            shell=False,
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
            ["docker compose", "--file", compose_file, "down"],
            shell=False,
            check=True,
            cwd=compose_file.parent,
        )


async def _get_projects_nodes(pool) -> dict[str, Any]:
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT uuid, workbench, prj_owner, users.name, users.email"
                ' FROM "projects"'
                " INNER JOIN users"
                " ON projects.prj_owner = users.id"
                " WHERE users.role != 'GUEST'"
            )
            typer.secho(
                f"found {cursor.rowcount} project rows, now getting project with valid node ids..."
            )
            project_db_rows = await cursor.fetchall()
        project_nodes = {
            project_uuid: {
                "nodes": list(workbench.keys()),
                "owner": prj_owner,
                "name": user_name,
                "email": user_email,
            }
            for project_uuid, workbench, prj_owner, user_name, user_email in project_db_rows
            if len(workbench) > 0
        }
        typer.echo(
            f"processed {cursor.rowcount} project rows, found {len(project_nodes)} valid projects."
        )
        return project_nodes


async def _get_files_from_project_nodes(
    pool, project_uuid: str, node_ids: list[str]
) -> set[tuple[str, int, datetime]]:
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            array = str([f"{project_uuid}/{n}%" for n in node_ids])
            await cursor.execute(
                "SELECT file_id, file_size, last_modified"
                ' FROM "file_meta_data"'
                f" WHERE file_meta_data.file_id LIKE any (array{array}) AND location_id = '0'"
            )

            # here we got all the files for that project uuid/node_ids combination
            file_rows = await cursor.fetchall()
            return {
                (file_id, file_size, parser.parse(last_modified or "2000-01-01"))
                for file_id, file_size, last_modified in file_rows
            }


async def _get_all_invalid_files_from_file_meta_data(
    pool,
) -> set[tuple[str, int, datetime]]:
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                'SELECT file_id, file_size, last_modified FROM "file_meta_data" '
                "WHERE file_meta_data.file_size < 1 OR file_meta_data.entity_tag IS NULL"
            )
            # here we got all the files for that project uuid/node_ids combination
            file_rows = await cursor.fetchall()
            return {
                (file_id, file_size, parser.parse(last_modified or "2000-01-01"))
                for file_id, file_size, last_modified in file_rows
            }


POWER_LABELS = {0: "B", 1: "KiB", 2: "MiB", 3: "GiB"}
LABELS_POWER = {v: k for k, v in POWER_LABELS.items()}


def convert_s3_label_to_bytes(s3_size: str) -> int:
    """convert 12MiB to 12 * 1024**2"""
    match = re.match(r"([0-9.]+)(\w+)", s3_size)
    if match:
        return int(float(match.groups()[0]) * 1024 ** LABELS_POWER[match.groups()[1]])
    return -1


async def limited_gather(*tasks, max_concurrency: int):
    wrapped_tasks = tasks
    if max_concurrency > 0:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def sem_task(task):
            async with semaphore:
                return await task

        wrapped_tasks = [sem_task(t) for t in tasks]

    return await asyncio.gather(*wrapped_tasks, return_exceptions=True)


async def _get_files_from_s3_backend(
    s3_endpoint: str,
    s3_access: str,
    s3_secret: str,
    s3_bucket: str,
    project_uuid: str,
    progress,
) -> set[tuple[str, int, datetime]]:
    s3_file_entries = set()
    try:
        # TODO: this could probably run faster if we maintain the client, and run successive commands in there
        command = (
            f"docker run --rm "
            f"--env MC_HOST_mys3='https://{s3_access}:{s3_secret}@{s3_endpoint}' "
            "minio/mc "
            f"ls --recursive mys3/{s3_bucket}/{project_uuid}/"
        )
        process = await asyncio.create_subprocess_shell(
            command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await process.communicate()
        decoded_stdout = stdout.decode()
        if decoded_stdout != b"":
            # formatted as:
            # [2021-09-07 04:35:49 UTC] 1.5GiB 05e821d1-2b4b-455f-86b6-9e197545c1ad/work.tgz
            # DATE_creation? size node_id/file_path.ext
            list_of_files = decoded_stdout.split("\n")
            for file in list_of_files:
                match = re.findall(r"\[(.+)\]\s+(\S+)\s+(.+)", file)
                if match:
                    last_modified, size, node_id_file = match[0]
                    s3_file_entries.add(
                        (
                            f"{project_uuid}/{node_id_file}",
                            convert_s3_label_to_bytes(size),
                            parser.parse(last_modified),
                        )
                    )

    except subprocess.CalledProcessError:
        pass

    progress.update(1)
    return s3_file_entries


def write_file(file_path: Path, data, fieldnames):
    with file_path.open("w", newline="") as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(fieldnames)
        csv_writer.writerows(data)


async def main_async(
    postgres_volume_name: str,
    postgres_username: str,
    postgres_password: str,
    s3_endpoint: str,
    s3_access: str,
    s3_secret: str,
    s3_bucket: str,
):
    # ---------------------- GET FILE ENTRIES FROM DB PROKECT TABLE -------------------------------------------------------------
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
                    _get_files_from_project_nodes(pool, project_uuid, prj_data["nodes"])
                    for project_uuid, prj_data in project_nodes.items()
                ]
            )
            all_invalid_files_in_file_meta_data = (
                await _get_all_invalid_files_from_file_meta_data(pool)
            )
    db_file_entries: set[tuple[str, int, datetime]] = set().union(
        *all_sets_of_file_entries
    )
    db_file_entries_path = Path.cwd() / f"{s3_endpoint}_db_file_entries.csv"
    write_file(
        db_file_entries_path, db_file_entries, ["file_id", "size", "last modified"]
    )
    typer.secho(
        f"processed {len(project_nodes)} projects, found {len(db_file_entries)} file entries, saved in {db_file_entries_path}",
        fg=typer.colors.YELLOW,
    )

    if all_invalid_files_in_file_meta_data:
        db_file_meta_data_invalid_entries_path = (
            Path.cwd() / f"{s3_endpoint}_db_file_meta_data_invalid_entries.csv"
        )
        write_file(
            db_file_meta_data_invalid_entries_path,
            all_invalid_files_in_file_meta_data,
            ["file_id", "size", "last modified"],
        )
        typer.secho(
            f"processed {len(all_invalid_files_in_file_meta_data)} INVALID file entries, saved in {db_file_meta_data_invalid_entries_path}",
            fg=typer.colors.YELLOW,
        )

    # ---------------------- GET FILE ENTRIES FROM S3 ---------------------------------------------------------------------
    # let's proceed with S3 backend: files are saved in BUCKET_NAME/projectID/nodeID/fileA.ext
    # Rationale: Similarly we list here all the files in each of the projects. And it goes faster to list them recursively.
    typer.echo(
        f"now connecting with S3 backend and getting files for {len(project_nodes)} projects..."
    )
    # pull first: prevents _get_files_from_s3_backend from pulling it and poluting outputs
    subprocess.run("docker pull minio/mc", shell=True, check=True)
    with typer.progressbar(length=len(project_nodes)) as progress:
        all_sets_in_s3 = await limited_gather(
            *[
                _get_files_from_s3_backend(
                    s3_endpoint, s3_access, s3_secret, s3_bucket, project_uuid, progress
                )
                for project_uuid in project_nodes
            ],
            max_concurrency=20,
        )
    s3_file_entries = set().union(*all_sets_in_s3)
    s3_file_entries_path = Path.cwd() / f"{s3_endpoint}_s3_file_entries.csv"
    write_file(
        s3_file_entries_path,
        s3_file_entries,
        fieldnames=["file_id", "size", "last_modified"],
    )
    typer.echo(
        f"processed {len(project_nodes)} projects, found {len(s3_file_entries)} file entries, saved in {s3_file_entries_path}"
    )

    # ---------------------- COMPARISON ---------------------------------------------------------------------
    db_file_ids = {db_file_id for db_file_id, _, _ in db_file_entries}
    s3_file_ids = {s3_file_id for s3_file_id, _, _ in s3_file_entries}
    common_files_uuids = db_file_ids.intersection(s3_file_ids)
    s3_missing_files_uuids = db_file_ids.difference(s3_file_ids)
    db_missing_files_uuids = s3_file_ids.difference(db_file_ids)
    typer.secho(
        f"{len(common_files_uuids)} files are the same in both system",
        fg=typer.colors.BLUE,
    )
    typer.secho(
        f"{len(s3_missing_files_uuids)} files are missing in S3", fg=typer.colors.RED
    )
    typer.secho(
        f"{len(db_missing_files_uuids)} files are missing in DB", fg=typer.colors.RED
    )

    # ------------------ WRITING REPORT --------------------------------------------
    consistent_files_path = Path.cwd() / f"{s3_endpoint}_consistent_files.csv"
    s3_missing_files_path = Path.cwd() / f"{s3_endpoint}_s3_missing_files.csv"
    db_missing_files_path = Path.cwd() / f"{s3_endpoint}_db_missing_files.csv"
    db_file_map: dict[str, tuple[int, datetime]] = {
        e[0]: e[1:] for e in db_file_entries
    }

    def order_by_owner(
        list_of_files_uuids: set[str],
    ) -> dict[tuple[str, str, str], list[tuple[str, int, datetime]]]:
        files_by_owner = defaultdict(list)
        for file_id in list_of_files_uuids:
            # project_id/node_id/file
            prj_uuid = file_id.split("/")[0]
            prj_data = project_nodes[prj_uuid]
            files_by_owner[
                (
                    prj_data["owner"],
                    prj_data["name"],
                    prj_data["email"],
                )
            ].append(file_id)
        return files_by_owner

    def write_to_file(path: Path, files_by_owner):
        with path.open("wt") as fp:
            fp.write("owner,name,email,file,size,last_modified\n")
            for (owner, name, email), files in files_by_owner.items():
                for file in files:
                    size, modified = db_file_map.get(file, ("?", "?"))
                    fp.write(f"{owner},{name},{email},{file}, {size}, {modified}\n")

    write_to_file(consistent_files_path, order_by_owner(common_files_uuids))
    write_to_file(s3_missing_files_path, order_by_owner(s3_missing_files_uuids))
    write_to_file(db_missing_files_path, order_by_owner(db_missing_files_uuids))


def main(
    postgres_volume_name: str,
    postgres_username: str,
    postgres_password: str,
    s3_endpoint: str,
    s3_access: str,
    s3_secret: str,
    s3_bucket: str,
):
    """Script to check consistency of the file storage backend in oSparc.

    requirements:
    - local docker volume containing a database from a deployment (see make import-db-from-docker-volume in /packages/postgres-database)

    1. From an osparc database, go over all projects, get the project IDs and Node IDs

    2. From the same database, now get all the files listed like projectID/nodeID from 1.

    3. We get a list of files that are needed for the current projects

    4. connect to the S3 backend, check that these files exist

    5. generate a report with: project uuid, owner, files missing in S3"""

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
