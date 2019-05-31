"""
    Object Relational Models and access to DB
"""

import enum
import logging
import uuid as uuidlib
from datetime import datetime
from typing import Dict, List, Mapping

import psycopg2.errors
import sqlalchemy as sa
from aiohttp import web
from aiopg.sa import Engine
from change_case import ChangeCase
from psycopg2 import IntegrityError
from sqlalchemy.sql import and_, select

from servicelib.application_keys import APP_DB_ENGINE_KEY
from simcore_sdk.models import metadata

from ..db_models import users
from ..utils import format_datetime, now_str
from .projects_exceptions import (ProjectInvalidRightsError,
                                  ProjectNotFoundError)

log = logging.getLogger(__name__)

# ENUM TYPES ----------------------------------------------------------------

class ProjectType(enum.Enum):
    """
        template: template project
        standard: standard project
    """
    TEMPLATE = "template"
    STANDARD = "standard"


# TABLES ----------------------------------------------------------------
#
#  We use a classical Mapping w/o using a Declarative system.
#
# See https://docs.sqlalchemy.org/en/latest/orm/mapping_styles.html#classical-mappings

projects = sa.Table("projects", metadata,
    sa.Column("id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("type", sa.Enum(ProjectType), nullable=False, default=ProjectType.STANDARD),

    sa.Column("uuid", sa.String, nullable=False, unique=True),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("description", sa.String, nullable=False),
    sa.Column("thumbnail", sa.String, nullable=False),
    sa.Column("prj_owner", sa.String, nullable=False),
    sa.Column("creation_date", sa.DateTime(), nullable=False, default=datetime.utcnow),
    sa.Column("last_change_date", sa.DateTime(), nullable=False, default=datetime.utcnow),
    sa.Column("workbench", sa.JSON, nullable=False)
)

user_to_projects = sa.Table("user_to_projects", metadata,
    sa.Column("id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("user_id", sa.BigInteger, sa.ForeignKey(users.c.id), nullable=False),
    sa.Column("project_id", sa.BigInteger, sa.ForeignKey(projects.c.id), nullable=False)
)


# TODO: check here how schema to model db works!?
def _convert_to_db_names(project_data: Dict) -> Dict:
    converted_args = {}
    for key, value in project_data.items():
        converted_args[ChangeCase.camel_to_snake(key)] = value
    return converted_args


def _convert_to_schema_names(project_db_data: Mapping) -> Dict:
    converted_args = {}
    for key, value in project_db_data.items():
        if key in ["type", "id"]:
            continue
        converted_value = value
        if isinstance(value, datetime):
            converted_value = format_datetime(value)
        converted_args[ChangeCase.snake_to_camel(key)] = converted_value
    return converted_args


class ProjectDB:
    # TODO: should implement similar model as services/web/server/src/simcore_service_webserver/login/storage.py
    # TODO: Move to projects_db as free functions
    # TODO: test all function return schema-compatible data

    @classmethod
    def get_engine(cls, request: web.Request) -> Engine:
        return request.config_dict.get(APP_DB_ENGINE_KEY)

    @classmethod
    async def add_projects(cls, projects_list: List[Dict], user_id: str, db_engine: Engine) -> List[str]:
        """
            adds all projects and assigns to a user

        If user_id is None, then project is added as Template

        """
        log.info("adding projects to database for user %s", user_id)
        uuids = []
        for prj in projects_list:
            prj_uuid = await cls.add_project(prj, user_id, db_engine)
            uuids.append(prj_uuid)
        return uuids

    @classmethod
    async def add_project(cls, prj: Dict, user_id: str, db_engine: Engine, *, force_project_uuid=False) -> str:
        """  Inserst a new project in the database and assigns it to a user (ownership) if provided.

        - If user_id is None, then project is added as template.
        - A valid uuid is automaticaly assigned to the project except if force_project_uuid=False. In the latter case,
        invalid uuid will raise an exception.

        :raises ProjectInvalidRightsError: Assigning project to an unregistered user
        :return: newly assigned project UUID
        :rtype: str
        """

        #pylint: disable=no-value-for-parameter
        user_email = await cls._get_user_email(user_id, db_engine)

        async with db_engine.acquire() as conn:
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
                "type": ProjectType.TEMPLATE if user_id is None else ProjectType.STANDARD,
            })

            # validate uuid
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

    @classmethod
    async def load_user_projects(cls, user_id: str, db_engine: Engine) -> List[Dict]:
        """ loads a project for a user

        """
        log.info("Loading projects for user %s", user_id)
        projects_list = []
        async with db_engine.acquire() as conn:
            joint_table = user_to_projects.join(projects)
            query = select([projects]).select_from(joint_table)\
                .where(user_to_projects.c.user_id == user_id)

            async for row in conn.execute(query):
                result_dict = {key:value for key,value in row.items()}
                log.debug("found project: %s", result_dict)
                projects_list.append(_convert_to_schema_names(result_dict))
        return projects_list

    @classmethod
    async def load_template_projects(cls, db_engine: Engine) -> List[Dict]:
        log.info("Loading template projects")
        projects_list = []
        async with db_engine.acquire() as conn:
            query = select([projects]).\
                where(projects.c.type == ProjectType.TEMPLATE)

            async for row in conn.execute(query):
                result_dict = {key:value for key,value in row.items()}
                log.debug("found project: %s", result_dict)
                projects_list.append(_convert_to_schema_names(result_dict))
        return projects_list

    @classmethod
    async def get_template_project(cls, project_uuid: str, db_engine: Engine) -> Dict:
        template_prj = None
        async with db_engine.acquire() as conn:
            query = select([projects]).where(
                and_(projects.c.type == ProjectType.TEMPLATE, projects.c.uuid == project_uuid)
            )
            result = await conn.execute(query)
            row = await result.first()
            template_prj = _convert_to_schema_names(row) if row else None

        return template_prj

    @classmethod
    async def get_user_project(cls, user_id: str, project_uuid: str, db_engine: Engine) -> Dict:
        """[summary]

        :raises ProjectNotFoundError: project is not assigned to user
        :return: schema-compliant project
        :rtype: Dict
        """
        log.info("Getting project %s for user %s", project_uuid, user_id)
        async with db_engine.acquire() as conn:
            joint_table = user_to_projects.join(projects)
            query = select([projects]).\
                select_from(joint_table).\
                    where(and_(projects.c.uuid == project_uuid, user_to_projects.c.user_id == user_id))
            result = await conn.execute(query)
            row = await result.first()
            if not row:
                raise ProjectNotFoundError(project_uuid)
            result_dict = {key:value for key,value in row.items()}
            log.debug("found project: %s", result_dict)
            return _convert_to_schema_names(result_dict)

    @classmethod
    async def update_user_project(cls, project_data: Dict, user_id: str, project_uuid: str, db_engine: Engine):
        """ updates a project from a user

        """
        log.info("Updating project %s for user %s", project_uuid, user_id)

        async with db_engine.acquire() as conn:
            joint_table = user_to_projects.join(projects)
            query = select([projects.c.id, projects.c.uuid]).\
                select_from(joint_table).\
                    where(and_(projects.c.uuid == project_uuid, user_to_projects.c.user_id == user_id))
            result = await conn.execute(query)

            # ensure we have found one
            row = await result.first()
            if not row:
                raise ProjectNotFoundError(project_uuid)

            # uuid can ONLY be set upon creation
            if row[projects.c.uuid] != project_data["uuid"]:
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
                    where(projects.c.id == row[projects.c.id])
            await conn.execute(query)

    @classmethod
    async def delete_user_project(cls, user_id: str, project_uuid: str, db_engine: Engine):
        """ deletes a project from a user

        """
        log.info("Deleting project %s for user %s", project_uuid, user_id)
        async with db_engine.acquire() as conn:
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

    @classmethod
    async def make_unique_project_uuid(cls, db_engine: Engine):
        async with db_engine.acquire() as conn:
            # generate a uuid
            # TODO: what if project already exists, shall we fail and ask to update??
            # TODO: add failure in case of hangs in while loop??
            # TODO: there is a small risk of two queries asking for the same id. better to retry?
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
    # TODO: refactor. separate model from storage API

    @classmethod
    async def _get_user_email(cls, user_id, db_engine):
        async with db_engine.acquire() as conn:
            result = await conn.execute(
                sa.select([users.c.email])\
                    .where(users.c.id == user_id)
            )
            row = await result.first()
        return row[users.c.email] if row else "Unknown"

__all__ = (
    "ProjectDB"
)
