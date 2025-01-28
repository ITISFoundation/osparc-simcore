from pathlib import Path

import typer
from db import (
    db_connection,
    get_project_and_files_to_migrate,
    insert_file_meta_data,
    insert_projects,
)
from models import Settings
from r_clone import assemble_config_file, sync_file


def main(config: Path = typer.Option(..., exists=True)):
    assert config.exists()  # nosec
    settings = Settings.load_from_file(config)
    typer.echo(
        f"Detected settings:\n{settings.model_dump_json(indent=2,warnings='none')}\n"
    )

    r_clone_config_path = assemble_config_file(
        # source
        source_access_key=settings.source.s3.access_key,
        source_secret_key=settings.source.s3.secret_key,
        source_endpoint=settings.source.s3.endpoint,
        source_provider=settings.source.s3.provider,
        # destination
        destination_access_key=settings.destination.s3.access_key,
        destination_secret_key=settings.destination.s3.secret_key,
        destination_endpoint=settings.destination.s3.endpoint,
        destination_provider=settings.destination.s3.provider,
    )
    typer.echo(f"Rclone config:\n{r_clone_config_path.read_text()}\n")

    with db_connection(settings.source.db) as src_db_conn, db_connection(
        settings.destination.db
    ) as dst_db_conn:
        (
            projects_to_migrate,
            files_meta_data_to_migrate,
        ) = get_project_and_files_to_migrate(
            project_uuid=settings.source.project_uuid,
            hidden_projects_for_user=settings.source.hidden_projects_for_user,
            src_conn=src_db_conn,
            dst_conn=dst_db_conn,
        )

        # Move data
        for file_meta_data in files_meta_data_to_migrate:
            # replacing user id with target one
            assert "user_id" in file_meta_data  # nosec
            file_meta_data["user_id"] = settings.destination.user_id

            sync_file(
                config_path=r_clone_config_path,
                s3_object=file_meta_data["object_name"],
                source_bucket=settings.source.s3.bucket,
                destination_bucket=settings.destination.s3.bucket,
            )
            insert_file_meta_data(connection=dst_db_conn, data=file_meta_data)

        # insert projects
        for project in projects_to_migrate:
            assert "prj_owner" in project  # nosec
            project["prj_owner"] = settings.destination.user_id
            # strip this field as it is not required
            assert "id" in project  # nosec
            del project["id"]

            assert "access_rights" in project  # nosec
            project["access_rights"] = {
                f"{settings.destination.user_gid}": {
                    "read": True,
                    "write": True,
                    "delete": True,
                }
            }

            insert_projects(connection=dst_db_conn, data=project)


if __name__ == "__main__":
    typer.run(main)
