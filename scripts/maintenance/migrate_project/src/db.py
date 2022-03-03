from collections import deque
from contextlib import contextmanager
from typing import Any, Deque, Dict, Iterator, Optional, Tuple
from uuid import UUID

from models import DBConfig
from simcore_postgres_database.models.file_meta_data import file_meta_data
from simcore_postgres_database.models.projects import projects
from sqlalchemy import and_, create_engine, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine.base import Connection
from sqlalchemy.engine.result import ResultProxy


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
    statemet = select([projects.c.id]).where(projects.c.uuid == f"{project_id}")
    exits = len(list(connection.execute(statemet))) > 0
    return exits


def _meta_data_exists_in_destination(connection: Connection, file_uuid: str) -> bool:
    statemet = select([file_meta_data.c.file_uuid]).where(
        file_meta_data.c.file_uuid == f"{file_uuid}"
    )
    exits = len(list(connection.execute(statemet))) > 0
    return exits


def _get_project(connection: Connection, project_uuid: UUID) -> ResultProxy:
    statemet = select([projects]).where(projects.c.uuid == f"{project_uuid}")
    return connection.execute(statemet)


def _get_hidden_project(connection: Connection, prj_owner: int) -> ResultProxy:
    statemet = select([projects]).where(
        and_(projects.c.prj_owner == prj_owner, projects.c.hidden == True)
    )
    return connection.execute(statemet)


def _get_file_meta_data_without_soft_links(
    connection: Connection, user_id: int, project_id: UUID
) -> ResultProxy:
    statemet = select([file_meta_data]).where(
        and_(
            file_meta_data.c.user_id == f"{user_id}",
            file_meta_data.c.project_id == f"{project_id}",
            file_meta_data.c.is_soft_link != True,
        )
    )
    return connection.execute(statemet)


def get_project_and_files_to_migrate(
    project_uuid: UUID,
    hidden_projects_for_user: Optional[int],
    src_conn: Connection,
    dst_conn: Connection,
) -> Tuple[Deque, Deque]:
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
        print(f"\n\n>>>>>>>>>SKIPPING, sync for {project=}\n\n")
        skipped_projects.append(project)
        raise Exception("could not continue, main project already exists on remote!")

    projects_to_migrate.append(project)

    if hidden_projects_for_user:
        # extract all hidden projects and check if they require syncing
        hidden_projects_cursor = _get_hidden_project(src_conn, hidden_projects_for_user)
        for hidden_result in hidden_projects_cursor:
            hidden_project = dict(hidden_result.items())
            if _project_uuid_exists_in_destination(dst_conn, hidden_project["uuid"]):
                print(f"\n\n>>>>>>>>>SKIPPING, sync for {project=}\n\n")
                skipped_projects.append(project)
                continue

            projects_to_migrate.append(hidden_project)

    # check file_meta_data in the projects to migrate
    for project in projects_to_migrate:
        user_id = project["prj_owner"]
        project_id = project["uuid"]

        files_metadata_cursor = _get_file_meta_data_without_soft_links(
            connection=src_conn, user_id=user_id, project_id=project_id
        )
        for result in files_metadata_cursor:
            file_meta_data = dict(result.items())
            file_uuid = file_meta_data["file_uuid"]

            if _meta_data_exists_in_destination(dst_conn, file_uuid):
                print(f"\n\n>>>>>>>>>SKIPPING, sync for {file_meta_data=}\n\n")
                skipped_files_meta_data.append(file_meta_data)
                continue

            files_meta_data_to_migrate.append(file_meta_data)

    if len(skipped_projects) > 0:
        print("SKIPPED projects", len(skipped_projects))
    if len(skipped_files_meta_data) > 0:
        print("SKIPPED files", len(skipped_files_meta_data))

    print("Projects to move", len(projects_to_migrate))
    print("Files to move", len(files_meta_data_to_migrate))
    print("Projects to SKIP", len(skipped_projects))
    print("Files to SKIP", len(skipped_files_meta_data))

    # if files and projects already exist
    if len(skipped_files_meta_data) > 0 or len(skipped_projects) > 0:
        print(
            "Projects skipped uuid(primary keys) listing:",
            [x["uuid"] for x in skipped_projects],
        )
        print(
            "File meta data skipped file_uuid(primary keys) listing:",
            [x["file_uuid"] for x in skipped_files_meta_data],
        )
        raise Exception(
            "Could not continue migration, some projects or files already exist."
        )

    return projects_to_migrate, files_meta_data_to_migrate


def insert_file_meta_data(connection: Connection, data: Dict[str, Any]) -> None:
    insert_stmt = insert(file_meta_data).values(**data)
    on_update_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[file_meta_data.c.file_uuid], set_=data
    )
    connection.execute(on_update_stmt)


def insert_projects(connection: Connection, data: Dict[str, Any]) -> None:
    insert_stmt = insert(projects).values(**data)
    on_update_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[projects.c.id], set_=data
    )
    connection.execute(on_update_stmt)
