import sqlalchemy
from aiopg.sa.engine import Engine
from models_library.projects import ProjectID
from models_library.users import UserID
from simcore_postgres_database.models.projects import projects

from .exceptions import ProjectNotFoundError


async def get_project_owner(engine: Engine, project_uuid: ProjectID) -> UserID:
    async with engine.acquire() as connection:
        stmt = sqlalchemy.select(projects.c.prj_owner).where(
            projects.c.uuid == f"{project_uuid}"
        )

        owner_id = await connection.scalar(stmt)
        if owner_id is None:
            raise ProjectNotFoundError(project_uuid=project_uuid)
        return owner_id
