""" Database API

    - Adds a layer to the postgres API with a focus on the projects data
    - Shall be used as entry point for all the queries to the database regarding projects

"""

import logging
import textwrap
import uuid as uuidlib
from collections import deque
from datetime import datetime
from enum import Enum
from typing import Dict, List, Mapping, Optional, Set, Union

import psycopg2.errors
import sqlalchemy as sa
from aiohttp import web
from aiopg.sa import Engine
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from change_case import ChangeCase
from sqlalchemy import literal_column
from sqlalchemy.sql import and_, select

from servicelib.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.webserver_models import ProjectType, projects

from ..db_models import GroupType, groups, study_tags, user_to_groups, users
from ..utils import format_datetime, now_str
from .projects_exceptions import (
    ProjectInvalidRightsError,
    ProjectNotFoundError,
    ProjectsException,
)
from .projects_fakes import Fake

log = logging.getLogger(__name__)

APP_PROJECT_DBAPI = __name__ + ".ProjectDBAPI"
DB_EXCLUSIVE_COLUMNS = [
    "type",
    "id",
    "published",
]


class ProjectAccessRights(Enum):
    OWNER = {"read": True, "write": True, "delete": True}
    COLLABORATOR = {"read": True, "write": True, "delete": False}
    VIEWER = {"read": True, "write": False, "delete": False}


def _check_project_permissions(
    project: Union[RowProxy, Dict],
    user_id: int,
    user_groups: List[RowProxy],
    permission: str,
) -> None:
    # compute access rights by order of priority all group > organizations > primary
    primary_group = next(filter(lambda x: x.type == GroupType.PRIMARY, user_groups))
    standard_groups = filter(lambda x: x.type == GroupType.STANDARD, user_groups)
    all_group = next(filter(lambda x: x.type == GroupType.EVERYONE, user_groups))

    if f"{primary_group.gid}" in project["access_rights"]:
        if not project["access_rights"][f"{primary_group.gid}"][permission]:
            raise ProjectInvalidRightsError(user_id, project["uuid"])
        return
    # let's check if standard groups are in there and take the most liberal rights
    standard_groups_permissions = []
    for group in standard_groups:
        if f"{group.gid}" in project["access_rights"]:
            standard_groups_permissions.append(
                project["access_rights"][f"{group.gid}"][permission]
            )
    if standard_groups_permissions:
        if not any(standard_groups_permissions):
            raise ProjectInvalidRightsError(user_id, project["uuid"])
        return

    if (
        not f"{all_group.gid}" in project["access_rights"]
        or not project["access_rights"][f"{all_group.gid}"][permission]
    ):
        raise ProjectInvalidRightsError(user_id, project["uuid"])


def _create_project_access_rights(
    gid: int, access: ProjectAccessRights
) -> Dict[str, Dict[str, bool]]:
    return {f"{gid}": access.value}


# TODO: check here how schema to model db works!?
def _convert_to_db_names(project_document_data: Dict) -> Dict:
    converted_args = {}
    exclude_keys = [
        "tags",
        "prjOwner",
    ]  # No column for tags, prjOwner is a foreign key in db
    for key, value in project_document_data.items():
        if not key in exclude_keys:
            converted_args[ChangeCase.camel_to_snake(key)] = value
    return converted_args


def _convert_to_schema_names(
    project_database_data: Mapping, user_email: str, **kwargs
) -> Dict:
    converted_args = {}
    for key, value in project_database_data.items():
        if key in DB_EXCLUSIVE_COLUMNS:
            continue
        converted_value = value
        if isinstance(value, datetime):
            converted_value = format_datetime(value)
        elif key == "prj_owner":
            # this entry has to be converted to the owner e-mail address
            converted_value = user_email
        converted_args[ChangeCase.snake_to_camel(key)] = converted_value
    converted_args.update(**kwargs)
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
        db_api._engine = engine  # pylint: disable=protected-access
        return db_api

    def _init_engine(self):
        # Delays creation of engine because it setup_db does it on_startup
        self._engine = self._app.get(APP_DB_ENGINE_KEY)
        if self._engine is None:
            raise ValueError("Database subsystem was not initialized")

    @property
    def engine(self) -> Engine:
        # lazy evaluation
        if self._engine is None:
            self._init_engine()
        return self._engine

    async def add_projects(self, projects_list: List[Dict], user_id: int) -> List[str]:
        """
            adds all projects and assigns to a user

        If user_id is None, then project is added as Template
        """
        log.info("adding projects to database for user %s", user_id)
        uuids = []
        for prj in projects_list:
            prj = await self.add_project(prj, user_id)
            uuids.append(prj["uuid"])
        return uuids

    async def add_project(
        self,
        prj: Dict,
        user_id: int,
        *,
        force_project_uuid=False,
        force_as_template=False,
    ) -> Dict:
        """Inserts a new project in the database and, if a user is specified, it assigns ownership

        - A valid uuid is automaticaly assigned to the project except if force_project_uuid=False. In the latter case,
        invalid uuid will raise an exception.

        :param prj: schema-compliant project data
        :type prj: Dict
        :param user_id: database's user identifier
        :type user_id: int
        :param force_project_uuid: enforces valid uuid, defaults to False
        :type force_project_uuid: bool, optional
        :param force_as_template: adds data as template, defaults to False
        :type force_as_template: bool, optional
        :raises ProjectInvalidRightsError: ssigning project to an unregistered user
        :return: newly assigned project UUID
        :rtype: str
        """
        # pylint: disable=no-value-for-parameter
        async with self.engine.acquire() as conn:
            # TODO: check security of this query with args. Hard-code values?
            # TODO: check best rollback design. see transaction.begin...
            # TODO: check if template, otherwise standard (e.g. template-  prefix in uuid)
            prj.update(
                {
                    "creationDate": now_str(),
                    "lastChangeDate": now_str(),
                }
            )
            kargs = _convert_to_db_names(prj)
            kargs.update(
                {
                    "type": ProjectType.TEMPLATE
                    if (force_as_template or user_id is None)
                    else ProjectType.STANDARD,
                    "prj_owner": user_id if user_id else None,
                }
            )
            # validate access_rights. are the gids valid? also ensure prj_owner is in there
            if user_id:
                primary_gid = await self._get_user_primary_group_gid(conn, user_id)
                kargs["access_rights"].update(
                    _create_project_access_rights(
                        primary_gid, ProjectAccessRights.OWNER
                    )
                )

            # must be valid uuid
            try:
                uuidlib.UUID(kargs.get("uuid"))
            except ValueError:
                if force_project_uuid:
                    raise
                kargs["uuid"] = str(uuidlib.uuid1())

            # insert project
            retry = True
            while retry:
                try:
                    query = projects.insert().values(**kargs)
                    result = await conn.execute(query)
                    await result.first()
                    retry = False
                except psycopg2.errors.UniqueViolation as err:  # pylint: disable=no-member
                    if (
                        err.diag.constraint_name != "projects_uuid_key"
                        or force_project_uuid
                    ):
                        raise
                    kargs["uuid"] = str(uuidlib.uuid1())
                    retry = True

            # Updated values
            user_email = await self._get_user_email(conn, user_id)
            prj = _convert_to_schema_names(kargs, user_email)
            if not "tags" in prj:
                prj["tags"] = []
            return prj

    async def load_user_projects(self, user_id: int) -> List[Dict]:
        log.info("Loading projects for user %s", user_id)
        async with self.engine.acquire() as conn:
            user_groups: List[RowProxy] = await self.__load_user_groups(conn, user_id)
            query = textwrap.dedent(
                f"""\
                SELECT *
                FROM projects
                WHERE projects.type != 'TEMPLATE'
                AND (jsonb_exists_any(projects.access_rights, array[{', '.join(f"'{group.gid}'" for group in user_groups)}])
                OR prj_owner = {user_id})
                """
            )
            projects_list = await self.__load_projects(
                conn, query, user_id, user_groups
            )

        return projects_list

    async def load_template_projects(
        self, user_id: int, *, only_published=False
    ) -> List[Dict]:
        log.info("Loading public template projects")

        # TODO: eliminate this and use mock to replace get_user_project instead
        projects_list = [prj.data for prj in Fake.projects.values() if prj.template]

        async with self.engine.acquire() as conn:
            user_groups: List[RowProxy] = await self.__load_user_groups(conn, user_id)

            # NOTE: in order to use specific postgresql function jsonb_exists_any we use raw call here
            query = textwrap.dedent(
                f"""\
                SELECT *
                FROM projects
                WHERE projects.type = 'TEMPLATE'
                {'AND projects.published ' if only_published else ''}
                AND (jsonb_exists_any(projects.access_rights, array[{', '.join(f"'{group.gid}'" for group in user_groups)}])
                OR prj_owner = {user_id})
                """
            )
            db_projects = await self.__load_projects(conn, query, user_id, user_groups)

            projects_list.extend(db_projects)

        return projects_list

    async def __load_user_groups(
        self, conn: SAConnection, user_id: int
    ) -> List[RowProxy]:
        user_groups: List[RowProxy] = []
        query = (
            select([groups])
            .select_from(groups.join(user_to_groups))
            .where(user_to_groups.c.uid == user_id)
        )
        async for row in conn.execute(query):
            user_groups.append(row)
        return user_groups

    async def __load_projects(
        self, conn: SAConnection, query: str, user_id: int, user_groups: List[RowProxy]
    ) -> List[Dict]:
        api_projects: List[Dict] = []  # API model-compatible projects
        db_projects: List[Dict] = []  # DB model-compatible projects
        async for row in conn.execute(query):
            try:
                _check_project_permissions(row, user_id, user_groups, "read")
            except ProjectInvalidRightsError:
                continue
            prj = dict(row.items())
            log.debug("found project: %s", prj)
            db_projects.append(prj)

        # NOTE: DO NOT nest _get_tags_by_project in async loop above !!!
        # FIXME: temporary avoids inner async loops issue https://github.com/aio-libs/aiopg/issues/535
        for db_prj in db_projects:
            db_prj["tags"] = await self._get_tags_by_project(
                conn, project_id=db_prj["id"]
            )
            user_email = await self._get_user_email(conn, db_prj["prj_owner"])
            api_projects.append(_convert_to_schema_names(db_prj, user_email))

        return api_projects

    async def _get_project(
        self,
        user_id: int,
        project_uuid: str,
        exclude_foreign: Optional[List] = None,
        include_templates: Optional[bool] = False,
    ) -> Dict:
        exclude_foreign = exclude_foreign or []
        async with self.engine.acquire() as conn:
            # this retrieves the projects where user is owner
            user_groups: List[RowProxy] = await self.__load_user_groups(conn, user_id)

            # NOTE: in order to use specific postgresql function jsonb_exists_any we use raw call here
            query = textwrap.dedent(
                f"""\
                SELECT *
                FROM projects
                WHERE
                {"" if include_templates else "projects.type != 'TEMPLATE' AND"}
                uuid = '{project_uuid}'
                AND (jsonb_exists_any(projects.access_rights, array[{', '.join(f"'{group.gid}'" for group in user_groups)}])
                OR prj_owner = {user_id})
                """
            )
            result = await conn.execute(query)
            project_row = await result.first()

            if not project_row:
                raise ProjectNotFoundError(project_uuid)

            # now carefuly check the access rights
            _check_project_permissions(project_row, user_id, user_groups, "read")

            project = dict(project_row.items())

            if "tags" not in exclude_foreign:
                tags = await self._get_tags_by_project(conn, project_id=project_row.id)
                project["tags"] = tags

            return project

    async def add_tag(self, user_id: int, project_uuid: str, tag_id: int) -> Dict:
        project = await self._get_project(user_id, project_uuid)
        async with self.engine.acquire() as conn:
            # pylint: disable=no-value-for-parameter
            query = study_tags.insert().values(study_id=project["id"], tag_id=tag_id)
            user_email = await self._get_user_email(conn, user_id)
            async with conn.execute(query) as result:
                if result.rowcount == 1:
                    project["tags"].append(tag_id)
                    return _convert_to_schema_names(project, user_email)
                raise ProjectsException()

    async def remove_tag(self, user_id: int, project_uuid: str, tag_id: int) -> Dict:
        project = await self._get_project(user_id, project_uuid)
        async with self.engine.acquire() as conn:
            user_email = await self._get_user_email(conn, user_id)
            # pylint: disable=no-value-for-parameter
            query = study_tags.delete().where(
                and_(
                    study_tags.c.study_id == project["id"],
                    study_tags.c.tag_id == tag_id,
                )
            )
            async with conn.execute(query):
                if tag_id in project["tags"]:
                    project["tags"].remove(tag_id)
                return _convert_to_schema_names(project, user_email)

    async def get_user_project(self, user_id: int, project_uuid: str) -> Dict:
        """Returns all projects *owned* by the user

            - prj_owner
            - Notice that a user can have access to a template but he might not onw it
            - Notice that a user can have access to a project where he/she has read access

        :raises ProjectNotFoundError: project is not assigned to user
        :return: schema-compliant project
        :rtype: Dict
        """
        # TODO: eliminate this and use mock to replace get_user_project instead
        prj = Fake.projects.get(project_uuid)
        if prj and not prj.template:
            return Fake.projects[project_uuid].data

        project = await self._get_project(user_id, project_uuid)
        async with self.engine.acquire() as conn:
            # pylint: disable=no-value-for-parameter
            user_email = await self._get_user_email(conn, project["prj_owner"])
            return _convert_to_schema_names(project, user_email)

    async def get_template_project(
        self, project_uuid: str, *, only_published=False
    ) -> Dict:
        # TODO: eliminate this and use mock to replace get_user_project instead
        prj = Fake.projects.get(project_uuid)
        if prj and prj.template:
            return prj.data

        template_prj = {}
        async with self.engine.acquire() as conn:
            if only_published:
                condition = and_(
                    projects.c.type == ProjectType.TEMPLATE,
                    projects.c.uuid == project_uuid,
                    projects.c.published == True,
                )
            else:
                condition = and_(
                    projects.c.type == ProjectType.TEMPLATE,
                    projects.c.uuid == project_uuid,
                )

            query = select([projects]).where(condition)

            result = await conn.execute(query)
            row = await result.first()
            if row:
                user_email = await self._get_user_email(conn, row["prj_owner"])
                template_prj = _convert_to_schema_names(row, user_email)
                tags = await self._get_tags_by_project(conn, project_id=row.id)
                template_prj["tags"] = tags

        return template_prj

    async def update_user_project(
        self,
        project_data: Dict,
        user_id: int,
        project_uuid: str,
        include_templates: Optional[bool] = False,
    ) -> Dict:
        """updates a project from a user"""
        log.info("Updating project %s for user %s", project_uuid, user_id)

        async with self.engine.acquire() as conn:
            row = await self._get_project(
                user_id,
                project_uuid,
                exclude_foreign=["tags"],
                include_templates=include_templates,
            )
            user_groups: List[RowProxy] = await self.__load_user_groups(conn, user_id)
            _check_project_permissions(row, user_id, user_groups, "write")
            # uuid can ONLY be set upon creation
            if row[projects.c.uuid.key] != project_data["uuid"]:
                raise ProjectInvalidRightsError(user_id, project_data["uuid"])
            # ensure the prj owner is always in the access rights
            owner_primary_gid = await self._get_user_primary_group_gid(
                conn, row[projects.c.prj_owner.key]
            )
            project_data["accessRights"].update(
                _create_project_access_rights(
                    owner_primary_gid, ProjectAccessRights.OWNER
                )
            )

            # update timestamps
            project_data["lastChangeDate"] = now_str()
            # now update it
            result = await conn.execute(
                # pylint: disable=no-value-for-parameter
                projects.update()
                .values(**_convert_to_db_names(project_data))
                .where(projects.c.id == row[projects.c.id.key])
                .returning(literal_column("*"))
            )
            project: RowProxy = await result.fetchone()
            user_email = await self._get_user_email(conn, project.prj_owner)

            tags = await self._get_tags_by_project(
                conn, project_id=project[projects.c.id]
            )
            return _convert_to_schema_names(project, user_email, tags=tags)

    async def delete_user_project(self, user_id: int, project_uuid: str):
        log.info("Deleting project %s for user %s", project_uuid, user_id)
        project = await self._get_project(user_id, project_uuid, include_templates=True)
        async with self.engine.acquire() as conn:
            # if we have delete access we delete the project
            user_groups: List[RowProxy] = await self.__load_user_groups(conn, user_id)
            _check_project_permissions(project, user_id, user_groups, "delete")
            await conn.execute(
                # pylint: disable=no-value-for-parameter
                projects.delete().where(projects.c.uuid == project_uuid)
            )

    async def make_unique_project_uuid(self) -> str:
        """Generates a project identifier still not used in database

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
                    select([projects]).where(projects.c.uuid == project_uuid)
                )
                found = await result.first()
                if not found:
                    break
        return project_uuid

    async def _get_user_email(self, conn: SAConnection, user_id: Optional[int]) -> str:
        if not user_id:
            return "not_a_user@unknown.com"
        email: ResultProxy = await conn.scalar(
            sa.select([users.c.email]).where(users.c.id == user_id)
        )
        return email or "Unknown"

    async def _get_user_primary_group_gid(
        self, conn: SAConnection, user_id: int
    ) -> int:
        primary_gid: int = await conn.scalar(
            sa.select([users.c.primary_gid]).where(users.c.id == str(user_id))
        )
        return primary_gid

    async def _get_tags_by_project(self, conn: SAConnection, project_id: str) -> List:
        query = sa.select([study_tags.c.tag_id]).where(
            study_tags.c.study_id == project_id
        )
        return [row.tag_id async for row in conn.execute(query)]

    async def get_all_node_ids_from_workbenches(
        self, project_uuid: str = None
    ) -> Set[str]:
        """Returns a set containing all the workbench node_ids from all projects

        If a project_uuid is passed, only that project's workbench nodes will be included
        """

        if project_uuid is None:
            query = "SELECT json_object_keys(projects.workbench) FROM projects"
        else:
            query = f"SELECT json_object_keys(projects.workbench) FROM projects WHERE projects.uuid = '{project_uuid}'"

        async with self.engine.acquire() as conn:
            result = set()
            query_result = await conn.execute(query)
            async for row in query_result:
                result.update(set(row.values()))

            return result

    async def list_all_projects_by_uuid_for_user(self, user_id: int) -> List[str]:
        result = deque()
        async with self.engine.acquire() as conn:
            async for row in conn.execute(
                sa.select([projects.c.uuid]).where(projects.c.prj_owner == user_id)
            ):
                result.append(row[0])
            return list(result)

    async def update_project_without_enforcing_checks(
        self, project_data: Dict, project_uuid: str
    ) -> bool:
        """The garbage collector needs to alter the row without passing through the
        permissions layer."""
        async with self.engine.acquire() as conn:
            # update timestamps
            project_data["lastChangeDate"] = now_str()
            # now update it
            result = await conn.execute(
                # pylint: disable=no-value-for-parameter
                projects.update()
                .values(**_convert_to_db_names(project_data))
                .where(projects.c.uuid == project_uuid)
            )
            return result.rowcount == 1


def setup_projects_db(app: web.Application):
    db = ProjectDBAPI(app)
    app[APP_PROJECT_DBAPI] = db
