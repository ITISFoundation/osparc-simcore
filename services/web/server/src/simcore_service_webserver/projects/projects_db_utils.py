""" Database utils

"""
import asyncio
import logging
from copy import deepcopy
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Mapping, Optional, Union

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from models_library.projects import ProjectAtDB
from models_library.users import UserID
from models_library.utils.change_case import camel_to_snake, snake_to_camel
from pydantic import ValidationError
from simcore_postgres_database.models.projects_to_products import projects_to_products
from simcore_postgres_database.webserver_models import ProjectType, projects
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import select

from ..db_models import GroupType, groups, study_tags, user_to_groups, users
from ..users_exceptions import UserNotFoundError
from ..utils import format_datetime
from .project_models import ProjectDict, ProjectProxy
from .projects_exceptions import ProjectInvalidRightsError, ProjectNotFoundError
from .projects_utils import project_uses_available_services

logger = logging.getLogger(__name__)

DB_EXCLUSIVE_COLUMNS = ["type", "id", "published", "hidden"]
SCHEMA_NON_NULL_KEYS = ["thumbnail"]

PermissionStr = Literal["read", "write", "delete"]

ANY_USER_ID_SENTINEL = -1


class ProjectAccessRights(Enum):
    # NOTE: PC->SAN: enum with dict as values is unual. need to review
    OWNER = {"read": True, "write": True, "delete": True}
    COLLABORATOR = {"read": True, "write": True, "delete": False}
    VIEWER = {"read": True, "write": False, "delete": False}


def check_project_permissions(
    project: Union[ProjectProxy, ProjectDict],
    user_id: int,
    user_groups: list[RowProxy],
    permission: str,
) -> None:
    """
    :raises ProjectInvalidRightsError if check fails
    """

    if not permission:
        return

    operations_on_project = set(permission.split("|"))
    assert set(operations_on_project).issubset(set(PermissionStr.__args__))  # nosec

    #
    # Get primary_gid, standard_gids and everyone_gid for user_id
    #
    all_group = next(
        filter(lambda x: x.get("type") == GroupType.EVERYONE, user_groups), None
    )
    if all_group is None:
        raise ProjectInvalidRightsError(user_id, project.get("uuid"))

    everyone_gid = str(all_group["gid"])

    if user_id == ANY_USER_ID_SENTINEL:
        primary_gid = None
        standard_gids = []

    else:
        primary_group = next(
            filter(lambda x: x.get("type") == GroupType.PRIMARY, user_groups), None
        )
        if primary_group is None:
            # the user groups is missing entries
            raise ProjectInvalidRightsError(user_id, project.get("uuid"))

        standard_groups = filter(
            lambda x: x.get("type") == GroupType.STANDARD, user_groups
        )

        primary_gid = str(primary_group["gid"])
        standard_gids = [str(group["gid"]) for group in standard_groups]

    #
    # Composes access rights by order of priority all group > organizations > primary
    #
    project_access_rights = deepcopy(project.get("access_rights", {}))

    # access rights for everyone
    user_can = project_access_rights.get(
        everyone_gid, {"read": False, "write": False, "delete": False}
    )

    # access rights for standard groups
    for group_id in standard_gids:
        standard_project_access = project_access_rights.get(
            group_id, {"read": False, "write": False, "delete": False}
        )
        for operation in user_can.keys():
            user_can[operation] = (
                user_can[operation] or standard_project_access[operation]
            )
    # access rights for primary group
    primary_access_right = project_access_rights.get(
        primary_gid, {"read": False, "write": False, "delete": False}
    )
    for operation in user_can.keys():
        user_can[operation] = user_can[operation] or primary_access_right[operation]

    if any(not user_can[operation] for operation in operations_on_project):
        raise ProjectInvalidRightsError(user_id, project.get("uuid"))


def create_project_access_rights(
    gid: int, access: ProjectAccessRights
) -> dict[str, dict[str, bool]]:
    return {f"{gid}": access.value}


def convert_to_db_names(project_document_data: dict) -> dict:
    # NOTE: this has to be moved to a proper model. check here how schema to model db works!?
    # SEE: https://github.com/ITISFoundation/osparc-simcore/issues/3516
    converted_args = {}
    exclude_keys = [
        "tags",
        "prjOwner",
    ]  # No column for tags, prjOwner is a foreign key in db
    for key, value in project_document_data.items():
        if key not in exclude_keys:
            converted_args[camel_to_snake(key)] = value
    return converted_args


def convert_to_schema_names(
    project_database_data: Mapping, user_email: str, **kwargs
) -> dict:
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/3516
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

        if key in SCHEMA_NON_NULL_KEYS and value is None:
            converted_value = ""

        converted_args[snake_to_camel(key)] = converted_value
    converted_args.update(**kwargs)
    return converted_args


def assemble_array_groups(user_groups: list[RowProxy]) -> str:
    return (
        "array[]::text[]"
        if len(user_groups) == 0
        else f"""array[{', '.join(f"'{group.gid}'" for group in user_groups)}]"""
    )


class BaseProjectDB:
    @classmethod
    async def _get_everyone_group(cls, conn: SAConnection) -> RowProxy:
        result = await conn.execute(
            sa.select([groups]).where(groups.c.type == GroupType.EVERYONE)
        )
        row = await result.first()
        return row

    @classmethod
    async def _list_user_groups(
        cls, conn: SAConnection, user_id: int
    ) -> list[RowProxy]:
        user_groups: list[RowProxy] = []

        if user_id == ANY_USER_ID_SENTINEL:
            everyone_group = await cls._get_everyone_group(conn)
            assert everyone_group  # nosec
            user_groups.append(everyone_group)
        else:
            result = await conn.execute(
                select([groups])
                .select_from(groups.join(user_to_groups))
                .where(user_to_groups.c.uid == user_id)
            )
            user_groups = await result.fetchall()
        return user_groups

    @staticmethod
    async def _get_user_email(conn: SAConnection, user_id: Optional[int]) -> str:
        if not user_id:
            return "not_a_user@unknown.com"
        email = await conn.scalar(
            sa.select([users.c.email]).where(users.c.id == user_id)
        )
        assert isinstance(email, str) or email is None  # nosec
        return email or "Unknown"

    @staticmethod
    async def _get_user_primary_group_gid(conn: SAConnection, user_id: int) -> int:
        primary_gid = await conn.scalar(
            sa.select([users.c.primary_gid]).where(users.c.id == str(user_id))
        )
        if not primary_gid:
            raise UserNotFoundError(uid=user_id)
        assert isinstance(primary_gid, int)
        return primary_gid

    @staticmethod
    async def _get_tags_by_project(conn: SAConnection, project_id: str) -> list:
        query = sa.select([study_tags.c.tag_id]).where(
            study_tags.c.study_id == project_id
        )
        return [row.tag_id async for row in conn.execute(query)]

    @staticmethod
    async def _upsert_tags_in_project(
        conn: SAConnection, project_index_id: int, project_tags: list[int]
    ) -> None:
        for tag_id in project_tags:
            await conn.execute(
                pg_insert(study_tags)
                .values(
                    study_id=project_index_id,
                    tag_id=tag_id,
                )
                .on_conflict_do_nothing()
            )

    async def _execute_with_permission_check(
        self,
        conn: SAConnection,
        *,
        select_projects_query: str,
        user_id: int,
        user_groups: list[RowProxy],
        filter_by_services: Optional[list[dict]] = None,
    ) -> tuple[list[dict[str, Any]], list[ProjectType]]:
        api_projects: list[dict] = []  # API model-compatible projects
        db_projects: list[dict] = []  # DB model-compatible projects
        project_types: list[ProjectType] = []
        async for row in conn.execute(select_projects_query):
            try:
                check_project_permissions(row, user_id, user_groups, "read")

                await asyncio.get_event_loop().run_in_executor(
                    None, ProjectAtDB.from_orm, row
                )

            except ProjectInvalidRightsError:
                continue

            except ValidationError as exc:
                logger.warning(
                    "project  %s  failed validation, please check. error: %s",
                    f"{row.id=}",
                    exc,
                )
                continue

            prj: dict[str, Any] = dict(row.items())
            prj.pop("product_name", None)

            if (
                filter_by_services is not None
                and row[projects_to_products.c.product_name] is None
                and not await project_uses_available_services(prj, filter_by_services)
            ):
                logger.warning(
                    "Project %s will not be listed for user %s since it has no access rights"
                    " for one or more of the services that includes.",
                    f"{row.id=}",
                    f"{user_id=}",
                )
                continue
            db_projects.append(prj)

        # NOTE: DO NOT nest _get_tags_by_project in async loop above !!!
        # FIXME: temporary avoids inner async loops issue https://github.com/aio-libs/aiopg/issues/535
        for db_prj in db_projects:
            db_prj["tags"] = await self._get_tags_by_project(
                conn, project_id=db_prj["id"]
            )
            user_email = await self._get_user_email(conn, db_prj["prj_owner"])
            api_projects.append(convert_to_schema_names(db_prj, user_email))
            project_types.append(db_prj["type"])

        return (api_projects, project_types)

    async def _get_project(
        self,
        connection: SAConnection,
        user_id: UserID,
        project_uuid: str,
        exclude_foreign: Optional[list[str]] = None,
        for_update: bool = False,
        only_templates: bool = False,
        only_published: bool = False,
        check_permissions: PermissionStr = "read",
    ) -> dict:
        """
        raises ProjectNotFoundError if project does not exists
        raises ProjectInvalidRightsError if user_id does not have at 'check_permissions' access rights
        """
        exclude_foreign = exclude_foreign or []

        # this retrieves the projects where user is owner
        user_groups: list[RowProxy] = await self._list_user_groups(connection, user_id)

        # NOTE: ChatGPT helped in producing this entry
        conditions = sa.and_(
            projects.c.uuid == f"{project_uuid}",
            projects.c.type == f"{ProjectType.TEMPLATE.value}"
            if only_templates
            else True,
            sa.or_(
                projects.c.prj_owner == user_id,
                sa.text(
                    f"jsonb_exists_any(projects.access_rights, {assemble_array_groups(user_groups)})"
                ),
                sa.case(
                    [
                        (
                            only_published,
                            projects.c.published == "true",
                        )
                    ],
                    else_=True,
                ),
            ),
        )
        query = select([projects]).where(conditions)
        if for_update:
            query = query.with_for_update()

        result = await connection.execute(query)
        project_row = await result.first()

        if not project_row:
            raise ProjectNotFoundError(
                project_uuid=project_uuid,
                search_context=f"{user_id=}, {only_templates=}, {only_published=}, {check_permissions=}",
            )

        # check the access rights
        check_project_permissions(project_row, user_id, user_groups, check_permissions)

        project: dict[str, Any] = dict(project_row.items())

        if "tags" not in exclude_foreign:
            tags = await self._get_tags_by_project(
                connection, project_id=project_row.id
            )
            project["tags"] = tags

        return project
