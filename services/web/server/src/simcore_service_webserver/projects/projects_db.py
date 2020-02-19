""" Database API

    - Adds a layer to the postgres API with a focus on the projects data
    - Shall be used as entry point for all the queries to the database regarding projects

"""

import logging
import uuid as uuidlib
from datetime import datetime
from typing import Dict, List, Mapping, Optional

import psycopg2.errors
import sqlalchemy as sa
from aiohttp import web
from aiopg.sa import Engine
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy

from change_case import ChangeCase
from psycopg2 import IntegrityError
from sqlalchemy.sql import and_, select

from servicelib.application_keys import APP_DB_ENGINE_KEY

from ..db_models import study_tags, users
from ..utils import format_datetime, now_str
from .projects_exceptions import (ProjectInvalidRightsError,
                                  ProjectNotFoundError, ProjectsException)
from .projects_fakes import Fake
from .projects_models import ProjectType, projects, user_to_projects

log = logging.getLogger(__name__)

APP_PROJECT_DBAPI  = __name__ + '.ProjectDBAPI'
DB_EXCLUSIVE_COLUMNS = ["type", "id", "published"]

# TODO: check here how schema to model db works!?
def _convert_to_db_names(project_document_data: Dict) -> Dict:
    converted_args = {}
    for key, value in project_document_data.items():
        if key != 'tags': # No column for tags
            converted_args[ChangeCase.camel_to_snake(key)] = value
    return converted_args

def _convert_to_schema_names(project_database_data: Mapping) -> Dict:
    converted_args = {}
    for key, value in project_database_data.items():
        if key in DB_EXCLUSIVE_COLUMNS:
            continue
        converted_value = value
        if isinstance(value, datetime):
            converted_value = format_datetime(value)
        converted_args[ChangeCase.snake_to_camel(key)] = converted_value
    return converted_args


# TODO: test all function return schema-compatible data
# TODO: is user_id str or int?
# TODO: systemaic user_id, project
# TODO: rename add_projects by create_projects
# FIXME: not clear when data is schema-compliant and db-compliant

class ProjectDBAPI:
    def __init__(self, app: web.Application):
        # TODO: shall be a weak pointer since it is also contained by app??
        self._app = app
        self._engine = app.get(APP_DB_ENGINE_KEY)

    @classmethod
    def init_from_engine(cls, engine: Engine):
        db_api = ProjectDBAPI({})
        db_api._engine = engine #pylint: disable=protected-access
        return db_api

    def _init_engine(self):
        # Delays creation of engine because it setup_db does it on_startup
        self._engine = self._app.get(APP_DB_ENGINE_KEY)
        if self._engine is None:
            raise ValueError("Postgres engine still not initialized ({}). Check setup_db".format(APP_DB_ENGINE_KEY))

    @property
    def engine(self) -> Engine:
        # lazy evaluation
        if self._engine is None:
            self._init_engine()
        return self._engine

    async def add_projects(self, projects_list: List[Dict], user_id: str) -> List[str]:
        """
            adds all projects and assigns to a user

        If user_id is None, then project is added as Template
        """
        log.info("adding projects to database for user %s", user_id)
        uuids = []
        for prj in projects_list:
            prj_uuid = await self.add_project(prj, user_id)
            uuids.append(prj_uuid)
        return uuids

    async def add_project(self, prj: Dict, user_id: str, *, force_project_uuid=False, force_as_template=False) -> str:
        """ Inserts a new project in the database and, if a user is specified, it assigns ownership

        - A valid uuid is automaticaly assigned to the project except if force_project_uuid=False. In the latter case,
        invalid uuid will raise an exception.

        :param prj: schema-compliant project data
        :type prj: Dict
        :param user_id: database's user identifier
        :type user_id: str
        :param force_project_uuid: enforces valid uuid, defaults to False
        :type force_project_uuid: bool, optional
        :param force_as_template: adds data as template, defaults to False
        :type force_as_template: bool, optional
        :raises ProjectInvalidRightsError: ssigning project to an unregistered user
        :return: newly assigned project UUID
        :rtype: str
        """
        #pylint: disable=no-value-for-parameter

        async with self.engine.acquire() as conn:
            user_email = await self._get_user_email(conn, user_id)

            # TODO: check security of this query with args. Hard-code values?
            # TODO: check best rollback design. see transaction.begin...
            # TODO: check if template, otherwise standard (e.g. template-  prefix in uuid)
            prj.update({
                "creationDate": now_str(),
                "lastChangeDate": now_str(),
                "prjOwner":user_email
            })
            kargs = _convert_to_db_names(prj)
            kargs.update({
                "type": ProjectType.TEMPLATE if (force_as_template or user_id is None) else ProjectType.STANDARD,
            })

            # must be valid uuid
            try:
                uuidlib.UUID(kargs.get('uuid'))
            except ValueError:
                if force_project_uuid:
                    raise
                kargs["uuid"] = str(uuidlib.uuid1())

            # insert project
            retry = True
            project_id = None
            while retry:
                try:
                    query = projects.insert().values(**kargs)
                    result = await conn.execute(query)
                    row = await result.first()
                    project_id = row[projects.c.id]
                    retry = False
                except psycopg2.errors.UniqueViolation as err:  # pylint: disable=no-member
                    if err.diag.constraint_name != "projects_uuid_key" or force_project_uuid:
                        raise
                    kargs["uuid"] = str(uuidlib.uuid1())
                    retry = True

            if user_id is not None:
                try:
                    query = user_to_projects.insert().values(
                        user_id=user_id,
                        project_id=project_id
                    )
                    await conn.execute(query)
                except IntegrityError as exc:
                    log.exception("Unregistered user trying to add project")

                    # rollback projects database
                    query = projects.delete().\
                        where(projects.c.id == project_id)
                    await conn.execute(query)

                    raise ProjectInvalidRightsError(user_id, prj["uuid"]) from exc

            # Updated values
            prj["uuid"] = kargs["uuid"]
            return prj["uuid"]

    async def load_user_projects(self, user_id: str, *, exclude_templates=True) -> List[Dict]:
        log.info("Loading projects for user %s", user_id)

        condition = user_to_projects.c.user_id == user_id
        if exclude_templates:
            condition = and_(condition,  projects.c.type != ProjectType.TEMPLATE )

        joint_table = user_to_projects.join(projects)
        query = select([projects]).select_from(joint_table).where(condition)

        async with self.engine.acquire() as conn:
            projects_list = await self.__load_projects(conn, query)

        return projects_list

    async def load_template_projects(self, *, only_published=False) -> List[Dict]:
        log.info("Loading public template projects")

        # TODO: eliminate this and use mock to replace get_user_project instead
        projects_list = [prj.data for prj in Fake.projects.values() if prj.template]

        async with self.engine.acquire() as conn:
            if only_published:
                expression = and_( projects.c.type == ProjectType.TEMPLATE, projects.c.published == True)
            else:
                expression = projects.c.type == ProjectType.TEMPLATE

            query = select([projects]).where(expression)
            projects_list.extend( await self.__load_projects(conn, query) )

        return projects_list

    async def __load_projects(self, conn: SAConnection, query) -> List[Dict]:
        projects_list: List[Dict] = []
        async for row in conn.execute(query):
            result_dict = dict(row.items())
            log.debug("found project: %s", result_dict)
            result_dict['tags'] = []
            projects_list.append(_convert_to_schema_names(result_dict))

        # NOTE: DO NOT nest _get_tags_by_project in async loop above !!!
        # FIXME: temporary avoids inner async loops issue https://github.com/aio-libs/aiopg/issues/535
        for prj in projects_list:
            prj['tags'] = await self._get_tags_by_project(conn, project_id=result_dict['id'])

        return projects_list

    async def _get_project(self, user_id: str, project_uuid: str, exclude_foreign: Optional[List]=None) -> Dict:
        exclude_foreign = exclude_foreign or []
        async with self.engine.acquire() as conn:
            joint_table = user_to_projects.join(projects)
            query = select([projects]).select_from(joint_table).where(
                and_(projects.c.uuid == project_uuid,
                     user_to_projects.c.user_id == user_id)
            )
            result = await conn.execute(query)
            project_row = await result.first()

            if not project_row:
                raise ProjectNotFoundError(project_uuid)

            project = dict(project_row.items())

            if 'tags' not in exclude_foreign:
                tags = await self._get_tags_by_project(conn, project_id=project_row.id)
                project['tags'] = tags

            return project

    async def add_tag(self, user_id: str, project_uuid: str, tag_id: int) -> Dict:
        project = await self._get_project(user_id, project_uuid)
        async with self.engine.acquire() as conn:
            # pylint: disable=no-value-for-parameter
            query = study_tags.insert().values(
                study_id=project['id'],
                tag_id=tag_id
            )
            async with conn.execute(query) as result:
                if result.rowcount == 1:
                    project['tags'].append(tag_id)
                    return _convert_to_schema_names(project)
                raise ProjectsException()

    async def remove_tag(self, user_id: str, project_uuid: str, tag_id: int) -> Dict:
        project = await self._get_project(user_id, project_uuid)
        async with self.engine.acquire() as conn:
            # pylint: disable=no-value-for-parameter
            query = study_tags.delete().where(
                and_(study_tags.c.study_id == project['id'], study_tags.c.tag_id == tag_id)
            )
            async with conn.execute(query):
                if tag_id in project['tags']:
                    project['tags'].remove(tag_id)
                return _convert_to_schema_names(project)

    async def get_user_project(self, user_id: str, project_uuid: str) -> Dict:
        """ Returns all projects *owned* by the user

            - A project is owned with it is mapped in user_to_projects list
            - prj_owner field is not
            - Notice that a user can have access to a template but he might not onw it

        :raises ProjectNotFoundError: project is not assigned to user
        :return: schema-compliant project
        :rtype: Dict
        """
        # TODO: eliminate this and use mock to replace get_user_project instead
        prj = Fake.projects.get(project_uuid)
        if prj and not prj.template:
            return Fake.projects[project_uuid].data

        project = await self._get_project(user_id, project_uuid)
        return _convert_to_schema_names(project)

    async def get_template_project(self, project_uuid: str, *, only_published=False) -> Dict:
        # TODO: eliminate this and use mock to replace get_user_project instead
        prj = Fake.projects.get(project_uuid)
        if prj and prj.template:
            return prj.data

        template_prj = None
        async with self.engine.acquire() as conn:
            if only_published:
                condition = and_(
                    projects.c.type == ProjectType.TEMPLATE,
                    projects.c.uuid == project_uuid,
                    projects.c.published==True)
            else:
                condition = and_(
                    projects.c.type == ProjectType.TEMPLATE,
                    projects.c.uuid == project_uuid)

            query = select([projects]).where(condition)

            result = await conn.execute(query)
            row = await result.first()
            if row:
                template_prj = _convert_to_schema_names(row)
                tags = await self._get_tags_by_project(conn, project_id=row.id)
                template_prj['tags'] = tags

        return template_prj

    async def get_project_workbench(self, project_uuid: str):
        async with self.engine.acquire() as conn:
            query = select([projects.c.workbench]).where(
                    projects.c.uuid == project_uuid
                    )
            result = await conn.execute(query)
            row = await result.first()
            if row:
                return row[projects.c.workbench]
        return {}

    async def update_user_project(self, project_data: Dict, user_id: str, project_uuid: str):
        """ updates a project from a user

        """
        log.info("Updating project %s for user %s", project_uuid, user_id)

        async with self.engine.acquire() as conn:
            row = await self._get_project(user_id, project_uuid, exclude_foreign=['tags'])

            # uuid can ONLY be set upon creation
            if row[projects.c.uuid.key] != project_data["uuid"]:
                # TODO: add message
                raise ProjectInvalidRightsError(user_id, project_data["uuid"])
            # TODO: should also take ownership???

            # update timestamps
            project_data["lastChangeDate"] = now_str()

            # now update it
            #FIXME: E1120:No value for argument 'dml' in method call
            # pylint: disable=E1120
            query = projects.update().\
                values(**_convert_to_db_names(project_data)).\
                    where(projects.c.id == row[projects.c.id.key])
            await conn.execute(query)

    async def pop_project(self, project_uuid) -> Dict:
        # TODO: delete projects and returns a copy
        pass

    async def delete_user_project(self, user_id: int, project_uuid: str):
        """ deletes a project from a user

        """
        log.info("Deleting project %s for user %s", project_uuid, user_id)
        async with self.engine.acquire() as conn:
            joint_table = user_to_projects.join(projects)
            query = select([projects.c.id, user_to_projects.c.id], use_labels=True).\
                select_from(joint_table).\
                    where(and_(projects.c.uuid == project_uuid, user_to_projects.c.user_id == user_id))
            result = await conn.execute(query)
            # ensure we have found one
            rows = await result.fetchall()

            if not rows:
                # no project found
                raise ProjectNotFoundError(project_uuid)

            if len(rows) == 1:
                row = rows[0]
                # now let's delete the link to the user
                #FIXME: E1120:No value for argument 'dml' in method call
                # pylint: disable=E1120
                project_id = row[user_to_projects.c.id]
                log.info("will delete row with project_id %s", project_id)
                query = user_to_projects.delete().\
                    where(user_to_projects.c.id == project_id)
                await conn.execute(query)

                query = user_to_projects.select().\
                    where(user_to_projects.c.project_id == row[projects.c.id])
                result = await conn.execute(query)
                remaining_users = await result.fetchall()
                if not remaining_users:
                    # only delete project if there are no other user mapped
                    query = projects.delete().\
                        where(projects.c.id == row[projects.c.id])
                    await conn.execute(query)

    async def make_unique_project_uuid(self) -> str:
        """ Generates a project identifier still not used in database

        WARNING: this method does not guarantee always unique id due to possible race condition
        (i.e. while client gets this uuid and uses it, another client might have used the same id already)

        :return: project UUID
        :rtype: str
        """
        async with self.engine.acquire() as conn:
            # TODO: add failure in case of hangs in while loop??
            while True:
                project_uuid = str(uuidlib.uuid1())
                result = await conn.execute(
                    select([projects])\
                        .where(projects.c.uuid==project_uuid)
                )
                found = await result.first()
                if not found:
                    break
        return project_uuid

    async def _get_user_email(self, conn: SAConnection, user_id: str) -> str:
        stmt = sa.select([users.c.email]).where(users.c.id == user_id)
        result: ResultProxy = await conn.execute(stmt)
        row: RowProxy = await result.first()
        return row[users.c.email] if row else "Unknown"

    async def _get_tags_by_project(self, conn: SAConnection, project_id: str) -> List:
        query = sa.select([study_tags.c.tag_id]).where(study_tags.c.study_id == project_id)
        rows = await (await conn.execute(query)).fetchall()
        return [ row.tag_id for row in rows ]


def setup_projects_db(app: web.Application):
    db = ProjectDBAPI(app)
    app[APP_PROJECT_DBAPI] = db
