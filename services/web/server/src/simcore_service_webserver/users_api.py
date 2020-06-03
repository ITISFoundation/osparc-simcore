import logging
from typing import Dict, List, Optional, Tuple

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa import SAConnection
from aiopg.sa.result import RowProxy
from sqlalchemy import and_, literal_column

from servicelib.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.login.cfg import get_storage

from .db_models import GroupType, groups, user_to_groups, users
from .users_exceptions import (
    GroupNotFoundError,
    UserInGroupNotFoundError,
    UserNotFoundError,
    UserInsufficientRightsError,
)
from .utils import gravatar_hash

logger = logging.getLogger(__name__)


GROUPS_SCHEMA_TO_DB = {
    "gid": "gid",
    "label": "name",
    "description": "description",
    "thumbnail": "thumbnail",
    "access_rights": "access_rights",
}


def _convert_groups_db_to_schema(db_row: RowProxy, **kwargs) -> Dict:
    converted_dict = {
        k: db_row[v] for k, v in GROUPS_SCHEMA_TO_DB.items() if v in db_row
    }
    converted_dict.update(**kwargs)
    return converted_dict


def _convert_groups_schema_to_db(schema: Dict) -> Dict:
    return {
        v: schema[k]
        for k, v in GROUPS_SCHEMA_TO_DB.items()
        if k in schema and k != "gid"
    }


def _convert_user_in_group_to_schema(row: RowProxy) -> Dict[str, str]:
    parts = row["name"].split(".") + [""]
    return {
        "first_name": parts[0],
        "last_name": parts[1],
        "login": row["email"],
        "gravatar_id": gravatar_hash(row["email"]),
    }


def _check_group_permissions(
    group: RowProxy, user_id: str, gid: str, permission: str
) -> None:
    if not group.access_rights[permission]:
        raise UserInsufficientRightsError(
            f"User {user_id} has insufficient rights for {permission} access to group {gid}"
        )


async def list_user_groups(
    app: web.Application, user_id: str
) -> Tuple[Dict[str, str], List[Dict[str, str]], Dict[str, str]]:
    """returns the user groups
    Returns:
        Tuple[List[Dict[str, str]]] -- [returns the user primary group, standard groups and the all group]
    """
    engine = app[APP_DB_ENGINE_KEY]
    primary_group = {}
    user_groups = []
    all_group = {}
    async with engine.acquire() as conn:
        query = (
            sa.select([groups, user_to_groups.c.access_rights])
            .select_from(
                user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid),
            )
            .where(user_to_groups.c.uid == user_id)
        )
        async for row in conn.execute(query):
            if row["type"] == GroupType.EVERYONE:
                all_group = _convert_groups_db_to_schema(row)
            elif row["type"] == GroupType.PRIMARY:
                primary_group = _convert_groups_db_to_schema(row)
            else:
                # only add if user has read access
                if row.access_rights["read"]:
                    user_groups.append(_convert_groups_db_to_schema(row))

    return (primary_group, user_groups, all_group)


async def _get_user_group(conn: SAConnection, user_id: str, gid: str) -> RowProxy:
    result = await conn.execute(
        sa.select([groups, user_to_groups.c.access_rights])
        .select_from(user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid))
        .where(and_(user_to_groups.c.uid == user_id, user_to_groups.c.gid == gid))
    )
    group = await result.fetchone()
    if not group:
        raise GroupNotFoundError(gid)
    return group


async def get_user_group(
    app: web.Application, user_id: str, gid: str
) -> Dict[str, str]:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        group: RowProxy = await _get_user_group(conn, user_id, gid)
        _check_group_permissions(group, user_id, gid, "read")
        return _convert_groups_db_to_schema(group)


async def create_user_group(
    app: web.Application, user_id: str, new_group: Dict
) -> Dict[str, str]:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        result = await conn.execute(
            sa.select([users.c.primary_gid]).where(users.c.id == user_id)
        )
        user: RowProxy = await result.fetchone()
        if not user:
            raise UserNotFoundError(user_id)
        result = await conn.execute(
            # pylint: disable=no-value-for-parameter
            groups.insert()
            .values(**_convert_groups_schema_to_db(new_group))
            .returning(literal_column("*"))
        )
        group: RowProxy = await result.fetchone()
        WRITE_ACCESS_RIGHTS = {"read": True, "write": True, "delete": True}
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            user_to_groups.insert().values(
                uid=user_id, gid=group.gid, access_rights=WRITE_ACCESS_RIGHTS,
            )
        )
    return _convert_groups_db_to_schema(group, access_rights=WRITE_ACCESS_RIGHTS)


async def update_user_group(
    app: web.Application, user_id: str, gid: str, new_group_values: Dict[str, str]
) -> Dict[str, str]:
    new_values = {
        k: v for k, v in _convert_groups_schema_to_db(new_group_values).items() if v
    }

    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        group = await _get_user_group(conn, user_id, gid)
        _check_group_permissions(group, user_id, gid, "write")

        result = await conn.execute(
            # pylint: disable=no-value-for-parameter
            groups.update()
            .values(**new_values)
            .where(groups.c.gid == group.gid)
            .returning(literal_column("*"))
        )
        updated_group = await result.fetchone()
        return _convert_groups_db_to_schema(
            updated_group, access_rights=group.access_rights
        )


async def delete_user_group(app: web.Application, user_id: str, gid: str) -> None:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        group = await _get_user_group(conn, user_id, gid)
        _check_group_permissions(group, user_id, gid, "delete")

        await conn.execute(
            # pylint: disable=no-value-for-parameter
            groups.delete().where(groups.c.gid == group.gid)
        )


async def list_users_in_group(
    app: web.Application, user_id: str, gid: str
) -> List[Dict[str, str]]:
    engine = app[APP_DB_ENGINE_KEY]

    async with engine.acquire() as conn:
        # first check if the group exists
        group: RowProxy = await _get_user_group(conn, user_id, gid)
        _check_group_permissions(group, user_id, gid, "read")
        # now get the list
        query = (
            sa.select([users, user_to_groups.c.access_rights])
            .select_from(users.join(user_to_groups))
            .where(user_to_groups.c.gid == gid)
        )
        users_list = [
            _convert_user_in_group_to_schema(row) async for row in conn.execute(query)
        ]
        return users_list


async def add_user_in_group(
    app: web.Application,
    user_id: str,
    gid: str,
    new_user_id: str,
    access_rights: Optional[Dict[str, bool]] = None,
) -> None:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        # first check if the group exists
        group: RowProxy = await _get_user_group(conn, user_id, gid)
        _check_group_permissions(group, user_id, gid, "write")
        # now check the new user exists
        users_count = await conn.scalar(
            # pylint: disable=no-value-for-parameter
            users.count().where(users.c.id == new_user_id)
        )
        if not users_count:
            raise UserInGroupNotFoundError(new_user_id, gid)
        # add the new user to the group now
        DEFAULT_ACCESS_RIGHTS = {"read": True, "write": False, "delete": False}
        user_access_rights = DEFAULT_ACCESS_RIGHTS
        if access_rights:
            user_access_rights.update(access_rights)
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            user_to_groups.insert().values(
                uid=new_user_id, gid=group.gid, access_rights=user_access_rights
            )
        )


async def _get_user_in_group_permissions(
    conn: SAConnection, user_id: str, gid: str, the_user_id_in_group: str
) -> RowProxy:

    # now get the user
    result = await conn.execute(
        sa.select([users, user_to_groups.c.access_rights])
        .select_from(users.join(user_to_groups, users.c.id == user_to_groups.c.uid))
        .where(and_(user_to_groups.c.gid == gid, users.c.id == the_user_id_in_group))
    )
    the_user: RowProxy = await result.fetchone()
    if not the_user:
        raise UserInGroupNotFoundError(the_user_id_in_group, gid)
    return the_user


async def get_user_in_group(
    app: web.Application, user_id: str, gid: str, the_user_id_in_group: str
) -> Dict[str, str]:
    engine = app[APP_DB_ENGINE_KEY]

    async with engine.acquire() as conn:
        # first check if the group exists
        group: RowProxy = await _get_user_group(conn, user_id, gid)
        _check_group_permissions(group, user_id, gid, "read")
        # get the user with its permissions
        the_user: RowProxy = await _get_user_in_group_permissions(
            conn, user_id, gid, the_user_id_in_group
        )
        return _convert_user_in_group_to_schema(the_user)


async def update_user_in_group(
    app: web.Application,
    user_id: str,
    gid: str,
    the_user_id_in_group: str,
    new_values_for_user_in_group: Dict,
) -> Dict[str, str]:
    engine = app[APP_DB_ENGINE_KEY]

    async with engine.acquire() as conn:
        # first check if the group exists
        group: RowProxy = await _get_user_group(conn, user_id, gid)
        _check_group_permissions(group, user_id, gid, "write")
        # now check the user exists
        the_user: RowProxy = await _get_user_in_group_permissions(
            conn, user_id, gid, the_user_id_in_group
        )
        # modify the user
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            user_to_groups.update()
            .values(**new_values_for_user_in_group)
            .where(
                and_(
                    user_to_groups.c.uid == the_user_id_in_group,
                    user_to_groups.c.gid == gid,
                )
            )
        )
        return _convert_user_in_group_to_schema(the_user)


async def delete_user_in_group(
    app: web.Application, user_id: str, gid: str, the_user_id_in_group: str
) -> None:
    engine = app[APP_DB_ENGINE_KEY]

    async with engine.acquire() as conn:
        # first check if the group exists
        group: RowProxy = await _get_user_group(conn, user_id, gid)
        _check_group_permissions(group, user_id, gid, "delete")
        # check the user exists
        the_user: RowProxy = await _get_user_in_group_permissions(
            conn, user_id, gid, the_user_id_in_group
        )
        # delete him/her
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            user_to_groups.delete().where(
                and_(
                    user_to_groups.c.uid == the_user_id_in_group,
                    user_to_groups.c.gid == gid,
                )
            )
        )


async def is_user_guest(app: web.Application, user_id: int) -> bool:
    """Returns True if the user exists and is a GUEST"""
    db = get_storage(app)
    user = await db.get_user({"id": user_id})
    if not user:
        logger.warning("Could not find user with id '%s'", user_id)
        return False

    return UserRole(user["role"]) == UserRole.GUEST


async def delete_user(app: web.Application, user_id: int) -> None:
    """Deletes a user from the database if the user exists"""
    db = get_storage(app)
    user = await db.get_user({"id": user_id})
    if not user:
        logger.warning(
            "User with id '%s' could not be deleted because it does not exist", user_id
        )
        return

    await db.delete_user(user)
