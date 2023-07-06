import sqlalchemy
from aiopg.sa.connection import SAConnection
from models_library.projects import ProjectID
from models_library.users import UserID
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.utils_projects_metadata import DBProjectNotFoundError


async def get_project_owner(
    connection: SAConnection, project_uuid: ProjectID
) -> UserID:
    stmt = sqlalchemy.select(projects.c.prj_owner).where(
        projects.c.uuid == f"{project_uuid}"
    )

    owner_id = await connection.scalar(stmt)
    if owner_id is None:
        raise DBProjectNotFoundError(project_uuid)
    return owner_id
