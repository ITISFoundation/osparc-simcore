from collections import deque
from contextlib import contextmanager
from typing import Any, Deque, Iterator
from uuid import UUID

import typer
from models import DBConfig
from simcore_postgres_database.models.file_meta_data import file_meta_data
from simcore_postgres_database.models.projects import projects
from sqlalchemy import and_, create_engine, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine.base import Connection
from sqlalchemy.engine.cursor import ResultProxy


@contextmanager
def db_connection(db_config: DBConfig) -> Iterator[Connection]:
    engine = create_engine(
        f"postgresql://{db_config.user}:{db_config.password}@{db_config.address}/{db_config.database}",
        echo=True,
    )
    with engine.connect() as con:
        yield con


def _project_uuid_exists_in_destination(
    connection: Connection, project_id: str
) -> bool:
    query = select(projects.c.id).where(projects.c.uuid == f"{project_id}")
    exists = len(list(connection.execute(query))) > 0
    return exists


def _meta_data_exists_in_destination(connection: Connection, file_id: str) -> bool:
    query = select(file_meta_data.c.file_id).where(
        file_meta_data.c.file_id == f"{file_id}"
    )
    exists = len(list(connection.execute(query))) > 0
    return exists


def _get_project(connection: Connection, project_uuid: UUID) -> ResultProxy:
    return connection.execute(
        select(projects).where(projects.c.uuid == f"{project_uuid}")
    )


def _get_hidden_project(connection: Connection, prj_owner: int) -> ResultProxy:
    return connection.execute(
        select(projects).where(
            and_(projects.c.prj_owner == prj_owner, projects.c.hidden.is_(True))
        )
    )


def _get_file_meta_data_without_soft_links(
    connection: Connection, node_uuid: UUID, project_id: UUID
) -> ResultProxy:
    return connection.execute(
        select(file_meta_data).where(
            and_(
                file_meta_data.c.node_id == f"{node_uuid}",
                file_meta_data.c.project_id == f"{project_id}",
                file_meta_data.c.is_soft_link.is_not(True),
            )
        )
    )


def _format_message(message: str, color: str, bold: bool = False) -> None:
    formatted_message = typer.style(message, fg=color, bold=bold)
    typer.echo(formatted_message)


def _red_message(message: str) -> None:
    _format_message(message, typer.colors.RED, bold=True)


def _green_message(message: str) -> None:
    _format_message(message, typer.colors.GREEN)


def _project_summary(project: dict) -> str:
    return f"PROJECT: {project['uuid']} {project['name']}"


def _file_summary(file_meta_data: dict) -> str:
    return f"FILE: {file_meta_data['object_name']}"


def get_project_and_files_to_migrate(
    project_uuid: UUID,
    hidden_projects_for_user: int | None,
    src_conn: Connection,
    dst_conn: Connection,
) -> tuple[Deque, Deque]:
    skipped_projects = deque()
    skipped_files_meta_data = deque()

    projects_to_migrate = deque()
    files_meta_data_to_migrate = deque()

    user_project_selection = list(_get_project(src_conn, project_uuid))
    assert len(user_project_selection) == 1
    user_project = user_project_selection[0]

    project = dict(user_project.items())
    project_id = project["uuid"]

    if _project_uuid_exists_in_destination(dst_conn, project_id):
        error_message = f"main project {project['uuid']} already exists at destination!"
        _red_message(error_message)
        raise Exception(error_message)

    projects_to_migrate.append(project)

    if hidden_projects_for_user:
        # extract all hidden projects and check if they require syncing
        hidden_projects_cursor = _get_hidden_project(src_conn, hidden_projects_for_user)
        for hidden_result in hidden_projects_cursor:
            hidden_project = dict(hidden_result.items())
            if _project_uuid_exists_in_destination(dst_conn, hidden_project["uuid"]):
                _red_message(f"SKIPPING, sync for {_project_summary(project)}")
                skipped_projects.append(project)
                continue

            projects_to_migrate.append(hidden_project)

    # check file_meta_data in the projects to migrate
    for project in projects_to_migrate:
        project_id = project["uuid"]

        # Since multiple users can generate files in the project
        # and nodes can be deleted we copy over all the files that
        # are available in the current node.
        node_uuids = project["workbench"].keys()
        already_processed_file: set[str] = set()
        for node_uuid in node_uuids:
            for result in _get_file_meta_data_without_soft_links(
                connection=src_conn, node_uuid=node_uuid, project_id=project_id
            ):
                file_meta_data = dict(result.items())
                object_name = file_meta_data["object_name"]
                if object_name in already_processed_file:
                    continue
                already_processed_file.add(object_name)

                if _meta_data_exists_in_destination(dst_conn, object_name):
                    _red_message(f"SKIPPING, sync for {_file_summary(file_meta_data)}")
                    skipped_files_meta_data.append(file_meta_data)
                    continue

                files_meta_data_to_migrate.append(file_meta_data)

    if len(skipped_projects) > 0:
        _red_message("SKIPPED projects count %s" % len(skipped_projects))
    if len(skipped_files_meta_data) > 0:
        _red_message("SKIPPED files count %s" % len(skipped_files_meta_data))

    _green_message("Projects to move %s" % len(projects_to_migrate))
    _green_message("Files to move %s" % len(files_meta_data_to_migrate))

    # if files and projects already exist
    if len(skipped_files_meta_data) > 0 or len(skipped_projects) > 0:
        _red_message(
            "Projects skipped uuid(primary keys) listing: %s"
            % [x["uuid"] for x in skipped_projects],
        )
        _red_message(
            "File meta data skipped object_name(primary keys) listing: %s"
            % [x["object_name"] for x in skipped_files_meta_data],
        )
        raise Exception(
            "Could not continue migration, some projects or files already exist."
        )

    return projects_to_migrate, files_meta_data_to_migrate


def insert_file_meta_data(connection: Connection, data: dict[str, Any]) -> None:
    connection.execute(insert(file_meta_data).values(**data))


def insert_projects(connection: Connection, data: dict[str, Any]) -> None:
    connection.execute(insert(projects).values(**data))
