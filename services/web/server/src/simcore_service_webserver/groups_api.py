import logging
from typing import Dict, List, Optional, Tuple

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa import SAConnection
from aiopg.sa.result import RowProxy
from sqlalchemy import and_, literal_column

from servicelib.application_keys import APP_DB_ENGINE_KEY

from .db_models import GroupType, groups, user_to_groups, users
from .groups_exceptions import (
    GroupNotFoundError,
    GroupsException,
    UserInGroupNotFoundError,
)
from .groups_utils import (
    check_group_permissions,
    convert_groups_db_to_schema,
    convert_groups_schema_to_db,
    convert_user_in_group_to_schema,
)
from .users_exceptions import UserNotFoundError

logger = logging.getLogger(__name__)

DEFAULT_GROUP_READ_ACCESS_RIGHTS = {"read": True, "write": False, "delete": False}
DEFAULT_GROUP_OWNER_ACCESS_RIGHTS = {"read": True, "write": True, "delete": True}


async def list_user_groups(
    app: web.Application, user_id: int
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
                all_group = convert_groups_db_to_schema(row)
            elif row["type"] == GroupType.PRIMARY:
                primary_group = convert_groups_db_to_schema(row)
            else:
                # only add if user has read access
                if row.access_rights["read"]:
                    user_groups.append(convert_groups_db_to_schema(row))

    return (primary_group, user_groups, all_group)


async def _get_user_group(conn: SAConnection, user_id: int, gid: int) -> RowProxy:
    result = await conn.execute(
        sa.select([groups, user_to_groups.c.access_rights])
        .select_from(user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid))
        .where(and_(user_to_groups.c.uid == user_id, user_to_groups.c.gid == gid))
    )
    group = await result.fetchone()
    if not group:
        raise GroupNotFoundError(gid)
    return group


async def _get_user_from_email(app: web.Application, email: str) -> RowProxy:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        result = await conn.execute(sa.select([users]).where(users.c.email == email))
        user: RowProxy = await result.fetchone()
        if not user:
            raise UserNotFoundError(email=email)
        return user


async def get_user_group(
    app: web.Application, user_id: int, gid: int
) -> Dict[str, str]:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        group: RowProxy = await _get_user_group(conn, user_id, gid)
        check_group_permissions(group, user_id, gid, "read")
        return convert_groups_db_to_schema(group)


async def create_user_group(
    app: web.Application, user_id: int, new_group: Dict
) -> Dict[str, str]:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        result = await conn.execute(
            sa.select([users.c.primary_gid]).where(users.c.id == user_id)
        )
        user: RowProxy = await result.fetchone()
        if not user:
            raise UserNotFoundError(uid=user_id)
        result = await conn.execute(
            # pylint: disable=no-value-for-parameter
            groups.insert()
            .values(**convert_groups_schema_to_db(new_group))
            .returning(literal_column("*"))
        )
        group: RowProxy = await result.fetchone()
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            user_to_groups.insert().values(
                uid=user_id,
                gid=group.gid,
                access_rights=DEFAULT_GROUP_OWNER_ACCESS_RIGHTS,
            )
        )
    return convert_groups_db_to_schema(
        group, accessRights=DEFAULT_GROUP_OWNER_ACCESS_RIGHTS
    )


async def update_user_group(
    app: web.Application, user_id: int, gid: int, new_group_values: Dict[str, str]
) -> Dict[str, str]:
    new_values = {
        k: v for k, v in convert_groups_schema_to_db(new_group_values).items() if v
    }

    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        group = await _get_user_group(conn, user_id, gid)
        check_group_permissions(group, user_id, gid, "write")

        result = await conn.execute(
            # pylint: disable=no-value-for-parameter
            groups.update()
            .values(**new_values)
            .where(groups.c.gid == group.gid)
            .returning(literal_column("*"))
        )
        updated_group = await result.fetchone()
        return convert_groups_db_to_schema(
            updated_group, accessRights=group.access_rights
        )


async def delete_user_group(app: web.Application, user_id: int, gid: int) -> None:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        group = await _get_user_group(conn, user_id, gid)
        check_group_permissions(group, user_id, gid, "delete")

        await conn.execute(
            # pylint: disable=no-value-for-parameter
            groups.delete().where(groups.c.gid == group.gid)
        )


async def list_users_in_group(
    app: web.Application, user_id: int, gid: int
) -> List[Dict[str, str]]:
    engine = app[APP_DB_ENGINE_KEY]

    async with engine.acquire() as conn:
        # first check if the group exists
        group: RowProxy = await _get_user_group(conn, user_id, gid)
        check_group_permissions(group, user_id, gid, "read")
        # now get the list
        query = (
            sa.select([users, user_to_groups.c.access_rights])
            .select_from(users.join(user_to_groups))
            .where(user_to_groups.c.gid == gid)
        )
        users_list = [
            convert_user_in_group_to_schema(row) async for row in conn.execute(query)
        ]
        return users_list


async def add_user_in_group(
    app: web.Application,
    user_id: int,
    gid: int,
    *,
    new_user_id: Optional[int] = None,
    new_user_email: Optional[str] = None,
    access_rights: Optional[Dict[str, bool]] = None,
) -> None:
    if not new_user_id and not new_user_email:
        raise GroupsException("Invalid method call, missing user id or user email")

    if new_user_email:
        user: RowProxy = await _get_user_from_email(app, new_user_email)
        new_user_id = user["id"]

    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        # first check if the group exists
        group: RowProxy = await _get_user_group(conn, user_id, gid)
        check_group_permissions(group, user_id, gid, "write")
        # now check the new user exists
        users_count = await conn.scalar(
            # pylint: disable=no-value-for-parameter
            sa.select([sa.func.count()]).where(users.c.id == new_user_id)
        )
        if not users_count:
            raise UserInGroupNotFoundError(new_user_id, gid)  # type: ignore
        # add the new user to the group now
        user_access_rights = DEFAULT_GROUP_READ_ACCESS_RIGHTS
        if access_rights:
            user_access_rights.update(access_rights)
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            user_to_groups.insert().values(
                uid=new_user_id, gid=group.gid, access_rights=user_access_rights
            )
        )


async def _get_user_in_group_permissions(
    conn: SAConnection, gid: int, the_user_id_in_group: int
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
    app: web.Application, user_id: int, gid: int, the_user_id_in_group: int
) -> Dict[str, str]:
    engine = app[APP_DB_ENGINE_KEY]

    async with engine.acquire() as conn:
        # first check if the group exists
        group: RowProxy = await _get_user_group(conn, user_id, gid)
        check_group_permissions(group, user_id, gid, "read")
        # get the user with its permissions
        the_user: RowProxy = await _get_user_in_group_permissions(
            conn, gid, the_user_id_in_group
        )
        return convert_user_in_group_to_schema(the_user)


async def update_user_in_group(
    app: web.Application,
    user_id: int,
    gid: int,
    the_user_id_in_group: int,
    new_values_for_user_in_group: Dict,
) -> Dict[str, str]:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        # first check if the group exists
        group: RowProxy = await _get_user_group(conn, user_id, gid)
        check_group_permissions(group, user_id, gid, "write")
        # now check the user exists
        the_user: RowProxy = await _get_user_in_group_permissions(
            conn, gid, the_user_id_in_group
        )
        # modify the user access rights
        new_db_values = {"access_rights": new_values_for_user_in_group["accessRights"]}
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            user_to_groups.update()
            .values(**new_db_values)
            .where(
                and_(
                    user_to_groups.c.uid == the_user_id_in_group,
                    user_to_groups.c.gid == gid,
                )
            )
        )
        the_user = dict(the_user)
        the_user.update(**new_db_values)
        return convert_user_in_group_to_schema(the_user)


async def delete_user_in_group(
    app: web.Application, user_id: int, gid: int, the_user_id_in_group: int
) -> None:
    engine = app[APP_DB_ENGINE_KEY]

    async with engine.acquire() as conn:
        # first check if the group exists
        group: RowProxy = await _get_user_group(conn, user_id, gid)
        check_group_permissions(group, user_id, gid, "write")
        # check the user exists
        await _get_user_in_group_permissions(conn, gid, the_user_id_in_group)
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
