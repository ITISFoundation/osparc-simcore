from typing import Dict, List

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.connection import SAConnection
from sqlalchemy.sql import and_

from ..db_models import folder_to_project
from .projects_db import ProjectDBAPI, _convert_to_schema_names
from .projects_exceptions import ProjectsException

APP_PROJECT_FOLDER_DBAPI = __name__ + ".ProjectFolderDBAPI"


class ProjectFolderDB(ProjectDBAPI):
    async def add_folder_to_project(self, project):
        print("add_folder_to_project", project, project["uuid"])
        async with self.engine.acquire() as conn:
            project["folder"] = await self._get_folder_by_project(
                conn, project_uuid=project["uuid"]
            )
        return project

    async def add_folder_to_projects(self, projects):
        for project in projects:
            await self.add_folder_to_project(project)
        return projects

    async def set_folder(self, user_id: int, project_uuid: str, folder_id: int) -> Dict:
        async with self.engine.acquire() as conn:
            project = await self._get_project(
                conn, user_id, project_uuid, include_templates=True
            )

            folder = await self._get_folder_by_project(
                conn, project_uuid=project["uuid"]
            )
            if folder:
                query = (
                    folder_to_project.update()
                    .where(folder_to_project.c.project_uuid == project["uuid"])
                    .values(project_uuid=project["uuid"], folder_id=folder_id)
                )
            else:
                query = folder_to_project.insert().values(
                    project_uuid=project["uuid"], folder_id=folder_id
                )
            user_email = await self._get_user_email(conn, user_id)
            async with conn.execute(query) as result:
                if result.rowcount == 1:
                    project["folder"] = folder_id
                    return _convert_to_schema_names(project, user_email)
                raise ProjectsException()

    async def remove_folder(
        self, user_id: int, project_uuid: str, folder_id: int
    ) -> Dict:
        async with self.engine.acquire() as conn:
            project = await self._get_project(
                conn, user_id, project_uuid, include_templates=True
            )
            user_email = await self._get_user_email(conn, user_id)
            # pylint: disable=no-value-for-parameter
            query = folder_to_project.delete().where(
                and_(
                    folder_to_project.c.project_uuid == project["uuid"],
                    folder_to_project.c.folder_id == folder_id,
                )
            )
            async with conn.execute(query):
                if project["folder"] == folder_id:
                    project["folder"] = None
                return _convert_to_schema_names(project, user_email)

    @staticmethod
    async def _get_folder_by_project(conn: SAConnection, project_uuid: str) -> List:
        query = sa.select([folder_to_project.c.folder_id]).where(
            folder_to_project.c.project_uuid == project_uuid
        )
        async with conn.execute(query) as result:
            row = await result.first()
            return row["folder_id"] if row else None


def setup_projects_folder_db(app: web.Application):
    db = ProjectFolderDB(app)
    app[APP_PROJECT_FOLDER_DBAPI] = db
