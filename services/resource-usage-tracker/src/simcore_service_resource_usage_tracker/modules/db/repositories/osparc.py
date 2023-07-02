import logging

import sqlalchemy as sa
from models_library.projects import ProjectID
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import users

from ._base import BaseRepository

_logger = logging.getLogger(__name__)


class OSparcRepository(BaseRepository):
    async def get_user_email(self, user_id: int) -> str | None:
        async with self.db_engine.connect() as conn:
            result = await conn.execute(
                sa.select(users.c.email).where(users.c.id == user_id)
            )
            data = result.first()
            output: str | None = data[0] if data else None
            return output

    async def get_project_name_and_workbench(
        self, project_uuid: ProjectID
    ) -> tuple[str, dict] | None:
        async with self.db_engine.connect() as conn:
            result = await conn.execute(
                sa.select(projects.c.name, projects.c.workbench).where(
                    projects.c.uuid == f"{project_uuid}"
                )
            )
            output = result.first()
            if output:
                project_name, project_workbench = output
                return project_name, project_workbench
            return None
