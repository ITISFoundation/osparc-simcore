#! /usr/bin/env python3

"""Script to check consistency of the file storage backend in oSparc.



    1. From an osparc database, go over all projects, get the project IDs and Node IDs
    2. From the same database, now get all the files listed like projectID/nodeID from 1.
    3. We get a list of files that are needed for the current projects
    4. connect to the S3 backend, check that these files exist
    5. generate a report with: project uuid, owner, files missing in S3
"""
import os
import re
import subprocess
from pathlib import Path

import psycopg2
import typer


def main(
    postgres_volume_name: str,
    postgres_username: str,
    postgres_password: str,
    s3_endpoint: str,
    s3_access: str,
    s3_secret: str,
    s3_bucket: str,
):
    # setup postgres and adminer
    typer.echo(f"starting up database in localhost")
    compose_file = Path.cwd() / "consistency" / "docker-compose.yml"
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

    # wait a bit that the dockers are up
    # time.sleep(5)

    db_file_paths = set()
    # now the database is up, let's go through the projects table
    with psycopg2.connect(
        host="127.0.0.1",
        port=5432,
        database="simcoredb",
        user=postgres_username,
        password=postgres_password,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT uuid, workbench"
                ' FROM "projects"'
                " INNER JOIN users"
                " ON projects.prj_owner = users.id"
                " WHERE users.role != 'GUEST'"
            )
            typer.echo(
                f"found {cursor.rowcount} projects, now getting project/node ids..."
            )
            project_nodes = {}
            rows = cursor.fetchall()
            with typer.progressbar(rows) as progress:
                for row in progress:
                    project_uuid, workbench = row
                    project_nodes[project_uuid] = list(workbench.keys())
            typer.echo(
                f"processed {cursor.rowcount} projects, now looking for files in the file_meta_data table..."
            )

            with typer.progressbar(project_nodes) as progress:
                for project_uuid, node_ids in project_nodes.items():
                    array = str([f"{project_uuid}/{n}%" for n in node_ids])

                    if not node_ids:
                        continue
                    cursor.execute(
                        "SELECT file_uuid"
                        ' FROM "file_meta_data"'
                        f" WHERE file_meta_data.file_uuid LIKE any (array{array}) AND location_id = '0'"
                    )

                    # here we got all the files for that project uuid/node_ids combination
                    file_rows = cursor.fetchall()
                    for file in file_rows:
                        db_file_paths.add(file[0])
                progress.update(1)

    db_file_entries_path = Path.cwd() / "project_file_entries.txt"
    db_file_entries_path.write_text("\n".join(db_file_paths))
    typer.echo(
        f"processed {len(project_nodes)} projects, found {len(db_file_paths)} file entries, saved in {db_file_entries_path}"
    )

    # ok now we need to connect to s3
    typer.echo(
        f"now connecting with S3 backend and getting file for {len(project_nodes)} projects..."
    )
    s3_file_entries = set()
    with typer.progressbar(project_nodes) as progress:
        for project_uuid in progress:
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
                        partial_file_path = re.findall(r".* (.+)", file)
                        s3_file_entries.add(f"{project_uuid}/{partial_file_path}")

            except subprocess.CalledProcessError:
                pass
    s3_file_entries_path = Path.cwd() / "s3_file_entries.txt"
    s3_file_entries_path.write_text("\n".join(s3_file_entries))
    typer.echo(
        f"processed {len(project_nodes)} projects, found {len(s3_file_entries)} file entries, saved in {s3_file_entries_path}"
    )
    import pdb

    pdb.set_trace()

    # file_found = set()
    # file_missing = set()
    # with typer.progressbar(db_file_paths) as progress:
    #     for file_entry in progress:
    #         try:
    #             subprocess.run(
    #                 f"docker run "
    #                 f"--env MC_HOST_mys3='https://{s3_access}:{s3_secret}@{s3_endpoint}' "
    #                 "minio/mc "
    #                 f"ls --recursive mys3/{s3_bucket}/{file_entry}",
    #                 shell=True,
    #                 check=True,
    #                 capture_output=True,
    #             )
    #             file_found.add(file_entry)
    #         except subprocess.CalledProcessError:
    #             file_missing.add(file_entry)

    # typer.echo(
    #     f"processed {len(db_file_paths)} files. found {len(file_found)}, missing {len(file_missing)}"
    # )
    # missing_files = Path.cwd() / "missing_files.txt"
    # missing_files.write_text("\n".join(file_missing))


if __name__ == "__main__":
    typer.run(main)
