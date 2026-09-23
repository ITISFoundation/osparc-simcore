from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import quote_plus
from uuid import UUID

import typer
from models import DBConfig
from simcore_postgres_database.models.file_meta_data import file_meta_data
from simcore_postgres_database.models.projects import projects
from sqlalchemy import and_, create_engine, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine.base import Connection
from sqlalchemy.engine.cursor import ResultProxy


class MigrationPreconditionError(RuntimeError):
    pass


@contextmanager
def db_connection(db_config: DBConfig) -> Iterator[Connection]:
    user = quote_plus(db_config.user)
    password = quote_plus(db_config.password.get_secret_value())
    engine = create_engine(
        f"postgresql+psycopg2://{user}:{password}@{db_config.address}/{db_config.database}",
        echo=True,
    )
    with engine.connect() as con:
        yield con


def _project_uuid_exists_in_destination(connection: Connection, project_id: str) -> bool:
    query = select(projects.c.id).where(projects.c.uuid == f"{project_id}")
    return len(list(connection.execute(query))) > 0


def _meta_data_exists_in_destination(connection: Connection, file_id: str) -> bool:
    query = select(file_meta_data.c.file_id).where(file_meta_data.c.file_id == f"{file_id}")
    return len(list(connection.execute(query))) > 0


def _get_project(connection: Connection, project_uuid: UUID) -> ResultProxy:
    return connection.execute(select(projects).where(projects.c.uuid == f"{project_uuid}"))


def _get_hidden_project(connection: Connection, prj_owner: int) -> ResultProxy:
    return connection.execute(
        select(projects).where(and_(projects.c.prj_owner == prj_owner, projects.c.hidden.is_(True)))
    )


def _get_file_meta_data_without_soft_links(connection: Connection, node_uuid: UUID, project_id: UUID) -> ResultProxy:
    return connection.execute(
        select(file_meta_data).where(
            and_(
                file_meta_data.c.node_id == f"{node_uuid}",
                file_meta_data.c.project_id == f"{project_id}",
                file_meta_data.c.is_soft_link.is_not(True),
            )
        )
    )


def _format_message(message: str, color: str, *, bold: bool = False) -> None:
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


def _get_main_project_to_migrate(src_conn: Connection, dst_conn: Connection, project_uuid: UUID) -> dict[str, Any]:
    user_project_selection = list(_get_project(src_conn, project_uuid))
    assert len(user_project_selection) == 1
    project = dict(user_project_selection[0].items())

    if _project_uuid_exists_in_destination(dst_conn, project["uuid"]):
        error_message = f"main project {project['uuid']} already exists at destination!"
        _red_message(error_message)
        raise MigrationPreconditionError(error_message)

    return project


def _collect_projects_to_migrate(
    src_conn: Connection,
    dst_conn: Connection,
    project_uuid: UUID,
    hidden_projects_for_user: int | None,
) -> tuple[deque[dict[str, Any]], deque[dict[str, Any]]]:
    skipped_projects: deque[dict[str, Any]] = deque()
    projects_to_migrate: deque[dict[str, Any]] = deque([_get_main_project_to_migrate(src_conn, dst_conn, project_uuid)])

    if hidden_projects_for_user is None:
        return projects_to_migrate, skipped_projects

    hidden_projects_cursor = _get_hidden_project(src_conn, hidden_projects_for_user)
    for hidden_result in hidden_projects_cursor:
        hidden_project = dict(hidden_result.items())
        if _project_uuid_exists_in_destination(dst_conn, hidden_project["uuid"]):
            _red_message(f"SKIPPING, sync for {_project_summary(hidden_project)}")
            skipped_projects.append(hidden_project)
            continue

        projects_to_migrate.append(hidden_project)

    return projects_to_migrate, skipped_projects


def _collect_files_to_migrate(
    src_conn: Connection,
    dst_conn: Connection,
    projects_to_migrate: deque[dict[str, Any]],
) -> tuple[deque[dict[str, Any]], deque[dict[str, Any]]]:
    skipped_files_meta_data: deque[dict[str, Any]] = deque()
    files_meta_data_to_migrate: deque[dict[str, Any]] = deque()

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

    return files_meta_data_to_migrate, skipped_files_meta_data


def _report_summary(
    projects_to_migrate: deque[dict[str, Any]],
    skipped_projects: deque[dict[str, Any]],
    files_meta_data_to_migrate: deque[dict[str, Any]],
    skipped_files_meta_data: deque[dict[str, Any]],
) -> None:
    if skipped_projects:
        _red_message(f"SKIPPED projects count {len(skipped_projects)}")
    if skipped_files_meta_data:
        _red_message(f"SKIPPED files count {len(skipped_files_meta_data)}")

    _green_message(f"Projects to move {len(projects_to_migrate)}")
    _green_message(f"Files to move {len(files_meta_data_to_migrate)}")


def _raise_if_skipped(
    skipped_projects: deque[dict[str, Any]],
    skipped_files_meta_data: deque[dict[str, Any]],
) -> None:
    if not skipped_files_meta_data and not skipped_projects:
        return

    _red_message(f"Projects skipped uuid(primary keys) listing: {[x['uuid'] for x in skipped_projects]}")
    _red_message(
        "File meta data skipped object_name(primary keys) listing: "
        f"{[x['object_name'] for x in skipped_files_meta_data]}"
    )
    error_message = "Could not continue migration, some projects or files already exist."
    raise MigrationPreconditionError(error_message)


def get_project_and_files_to_migrate(
    project_uuid: UUID,
    hidden_projects_for_user: int | None,
    src_conn: Connection,
    dst_conn: Connection,
) -> tuple[deque, deque]:
    projects_to_migrate, skipped_projects = _collect_projects_to_migrate(
        src_conn=src_conn,
        dst_conn=dst_conn,
        project_uuid=project_uuid,
        hidden_projects_for_user=hidden_projects_for_user,
    )
    files_meta_data_to_migrate, skipped_files_meta_data = _collect_files_to_migrate(
        src_conn=src_conn,
        dst_conn=dst_conn,
        projects_to_migrate=projects_to_migrate,
    )
    _report_summary(
        projects_to_migrate=projects_to_migrate,
        skipped_projects=skipped_projects,
        files_meta_data_to_migrate=files_meta_data_to_migrate,
        skipped_files_meta_data=skipped_files_meta_data,
    )
    _raise_if_skipped(
        skipped_projects=skipped_projects,
        skipped_files_meta_data=skipped_files_meta_data,
    )

    return projects_to_migrate, files_meta_data_to_migrate


def insert_file_meta_data(connection: Connection, data: dict[str, Any]) -> None:
    connection.execute(insert(file_meta_data).values(**data))


def insert_projects(connection: Connection, data: dict[str, Any]) -> None:
    connection.execute(insert(projects).values(**data))
