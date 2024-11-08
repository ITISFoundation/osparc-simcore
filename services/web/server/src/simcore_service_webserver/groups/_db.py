import re
from typing import Any

import sqlalchemy as sa
from aiopg.sa import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from models_library.groups import GroupAtDB
from models_library.users import GroupID, UserID
from simcore_postgres_database.errors import UniqueViolation
from simcore_postgres_database.utils_products import get_or_create_product_group
from sqlalchemy import and_, literal_column
from sqlalchemy.dialects.postgresql import insert

from ..db.models import GroupType, groups, user_to_groups, users
from ..users.exceptions import UserNotFoundError
from ._users import convert_user_in_group_to_schema
from ._utils import (
    AccessRightsDict,
    check_group_permissions,
    convert_groups_db_to_schema,
    convert_groups_schema_to_db,
)
from .exceptions import (
    GroupNotFoundError,
    UserAlreadyInGroupError,
    UserInGroupNotFoundError,
)

_DEFAULT_PRODUCT_GROUP_ACCESS_RIGHTS = AccessRightsDict(
    read=False,
    write=False,
    delete=False,
)

_DEFAULT_GROUP_READ_ACCESS_RIGHTS = AccessRightsDict(
    read=True,
    write=False,
    delete=False,
)
_DEFAULT_GROUP_OWNER_ACCESS_RIGHTS = AccessRightsDict(
    read=True,
    write=True,
    delete=True,
)


async def _get_user_group(
    conn: SAConnection, user_id: UserID, gid: GroupID
) -> RowProxy:
    result = await conn.execute(
        sa.select(groups, user_to_groups.c.access_rights)
        .select_from(user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid))
        .where(and_(user_to_groups.c.uid == user_id, user_to_groups.c.gid == gid))
    )
    group = await result.fetchone()
    if not group:
        raise GroupNotFoundError(gid=gid)
    assert isinstance(group, RowProxy)  # nosec
    return group


async def get_user_from_email(conn: SAConnection, email: str) -> RowProxy:
    result = await conn.execute(sa.select(users).where(users.c.email == email))
    user = await result.fetchone()
    if not user:
        raise UserNotFoundError(email=email)
    assert isinstance(user, RowProxy)  # nosec
    return user


#
# USER GROUPS: standard operations
#


async def get_all_user_groups_with_read_access(
    conn: SAConnection, user_id: UserID
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """
    Returns the user primary group, standard groups and the all group
    """
    primary_group = {}
    user_groups = []
    all_group = {}

    query = (
        sa.select(groups, user_to_groups.c.access_rights)
        .select_from(
            user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid),
        )
        .where(user_to_groups.c.uid == user_id)
    )
    row: RowProxy
    async for row in conn.execute(query):
        if row.type == GroupType.EVERYONE:
            assert row.access_rights["read"]  # nosec
            all_group = convert_groups_db_to_schema(row)

        elif row.type == GroupType.PRIMARY:
            assert row.access_rights["read"]  # nosec
            primary_group = convert_groups_db_to_schema(row)

        else:
            assert row.type == GroupType.STANDARD  # nosec
            # only add if user has read access
            if row.access_rights["read"]:
                user_groups.append(convert_groups_db_to_schema(row))

    return (primary_group, user_groups, all_group)


async def get_all_user_groups(conn: SAConnection, user_id: UserID) -> list[GroupAtDB]:
    """
    Returns all user groups
    """
    result = await conn.execute(
        sa.select(groups)
        .select_from(
            user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid),
        )
        .where(user_to_groups.c.uid == user_id)
    )
    rows = await result.fetchall() or []
    return [GroupAtDB.model_validate(row) for row in rows]


async def get_user_group(
    conn: SAConnection, user_id: UserID, gid: GroupID
) -> dict[str, str]:
    """
    Gets group gid if user associated to it and has read access

    raises GroupNotFoundError
    raises UserInsufficientRightsError
    """
    group: RowProxy = await _get_user_group(conn, user_id, gid)
    check_group_permissions(group, user_id, gid, "read")
    return convert_groups_db_to_schema(group)


async def get_product_group_for_user(
    conn: SAConnection, user_id: UserID, product_gid: GroupID
) -> dict[str, str]:
    """
    Returns product's group if user belongs to it, otherwise it
    raises GroupNotFoundError
    """
    group: RowProxy = await _get_user_group(conn, user_id, product_gid)
    return convert_groups_db_to_schema(group)


async def create_user_group(
    conn: SAConnection, user_id: UserID, new_group: dict
) -> dict[str, Any]:
    result = await conn.execute(
        sa.select(users.c.primary_gid).where(users.c.id == user_id)
    )
    user: RowProxy | None = await result.fetchone()
    if not user:
        raise UserNotFoundError(uid=user_id)
    result = await conn.execute(
        # pylint: disable=no-value-for-parameter
        groups.insert()
        .values(**convert_groups_schema_to_db(new_group))
        .returning(literal_column("*"))
    )
    group: RowProxy | None = await result.fetchone()
    assert group  # nosec

    await conn.execute(
        # pylint: disable=no-value-for-parameter
        user_to_groups.insert().values(
            uid=user_id,
            gid=group.gid,
            access_rights=_DEFAULT_GROUP_OWNER_ACCESS_RIGHTS,
        )
    )
    return convert_groups_db_to_schema(
        group, accessRights=_DEFAULT_GROUP_OWNER_ACCESS_RIGHTS
    )


async def update_user_group(
    conn: SAConnection, user_id: UserID, gid: GroupID, new_group_values: dict[str, str]
) -> dict[str, str]:
    new_values = {
        k: v for k, v in convert_groups_schema_to_db(new_group_values).items() if v
    }

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
    assert updated_group  # nosec

    return convert_groups_db_to_schema(updated_group, accessRights=group.access_rights)


async def delete_user_group(conn: SAConnection, user_id: UserID, gid: GroupID) -> None:
    group = await _get_user_group(conn, user_id, gid)
    check_group_permissions(group, user_id, gid, "delete")

    await conn.execute(
        # pylint: disable=no-value-for-parameter
        groups.delete().where(groups.c.gid == group.gid)
    )


#
# USER GROUPS: Custom operations
#


async def list_users_in_group(
    conn: SAConnection, user_id: UserID, gid: GroupID
) -> list[dict[str, str]]:
    # first check if the group exists
    group: RowProxy = await _get_user_group(conn, user_id, gid)
    check_group_permissions(group, user_id, gid, "read")
    # now get the list
    query = (
        sa.select(users, user_to_groups.c.access_rights)
        .select_from(users.join(user_to_groups))
        .where(user_to_groups.c.gid == gid)
    )
    users_list = [
        convert_user_in_group_to_schema(row) async for row in conn.execute(query)
    ]
    return users_list


async def auto_add_user_to_groups(conn: SAConnection, user: dict) -> None:
    user_id: UserID = user["id"]

    # auto add user to the groups with the right rules
    # get the groups where there are inclusion rules and see if they apply
    query = sa.select(groups).where(groups.c.inclusion_rules != {})
    possible_group_ids = set()
    async for row in conn.execute(query):
        inclusion_rules = row[groups.c.inclusion_rules]
        for prop, rule_pattern in inclusion_rules.items():
            if prop not in user:
                continue
            if re.search(rule_pattern, user[prop]):
                possible_group_ids.add(row[groups.c.gid])

    # now add the user to these groups if possible
    for gid in possible_group_ids:
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            insert(user_to_groups)
            .values(
                uid=user_id,
                gid=gid,
                access_rights=_DEFAULT_GROUP_READ_ACCESS_RIGHTS,
            )
            .on_conflict_do_nothing()  # in case the user was already added
        )


async def auto_add_user_to_product_group(
    conn: SAConnection, user_id: UserID, product_name: str
) -> GroupID:
    product_group_id: GroupID = await get_or_create_product_group(conn, product_name)

    await conn.execute(
        # pylint: disable=no-value-for-parameter
        insert(user_to_groups)
        .values(
            uid=user_id,
            gid=product_group_id,
            access_rights=_DEFAULT_PRODUCT_GROUP_ACCESS_RIGHTS,
        )
        .on_conflict_do_nothing()  # in case the user was already added
    )
    return product_group_id


async def is_user_by_email_in_group(
    conn: SAConnection, email: str, group_id: GroupID
) -> bool:
    user_id = await conn.scalar(
        sa.select(users.c.id)
        .select_from(sa.join(user_to_groups, users, user_to_groups.c.uid == users.c.id))
        .where((users.c.email == email) & (user_to_groups.c.gid == group_id))
    )
    return user_id is not None


async def add_new_user_in_group(
    conn: SAConnection,
    user_id: UserID,
    gid: GroupID,
    *,
    new_user_id: UserID,
    access_rights: AccessRightsDict | None = None,
) -> None:
    """
    adds new_user (either by id or email) in group (with gid) owned by user_id
    """

    # first check if the group exists
    group: RowProxy = await _get_user_group(conn, user_id, gid)
    check_group_permissions(group, user_id, gid, "write")

    # now check the new user exists
    users_count = await conn.scalar(
        sa.select(sa.func.count()).where(users.c.id == new_user_id)
    )
    if not users_count:
        assert new_user_id is not None  # nosec
        raise UserInGroupNotFoundError(uid=new_user_id, gid=gid)

    # add the new user to the group now
    user_access_rights = _DEFAULT_GROUP_READ_ACCESS_RIGHTS
    if access_rights:
        user_access_rights.update(access_rights)

    try:
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            user_to_groups.insert().values(
                uid=new_user_id, gid=group.gid, access_rights=user_access_rights
            )
        )
    except UniqueViolation as exc:
        raise UserAlreadyInGroupError(
            uid=new_user_id, gid=gid, user_id=user_id, access_rights=access_rights
        ) from exc


async def _get_user_in_group_permissions(
    conn: SAConnection, gid: GroupID, the_user_id_in_group: int
) -> RowProxy:
    # now get the user
    result = await conn.execute(
        sa.select(users, user_to_groups.c.access_rights)
        .select_from(users.join(user_to_groups, users.c.id == user_to_groups.c.uid))
        .where(and_(user_to_groups.c.gid == gid, users.c.id == the_user_id_in_group))
    )
    the_user: RowProxy | None = await result.fetchone()
    if not the_user:
        raise UserInGroupNotFoundError(uid=the_user_id_in_group, gid=gid)
    return the_user


async def get_user_in_group(
    conn: SAConnection, user_id: UserID, gid: GroupID, the_user_id_in_group: int
) -> dict[str, str]:
    # first check if the group exists
    group: RowProxy = await _get_user_group(conn, user_id, gid)
    check_group_permissions(group, user_id, gid, "read")
    # get the user with its permissions
    the_user: RowProxy = await _get_user_in_group_permissions(
        conn, gid, the_user_id_in_group
    )
    return convert_user_in_group_to_schema(the_user)


async def update_user_in_group(
    conn: SAConnection,
    user_id: UserID,
    gid: GroupID,
    the_user_id_in_group: int,
    access_rights: dict,
) -> dict[str, str]:
    if not access_rights:
        msg = f"Cannot update empty {access_rights}"
        raise ValueError(msg)

    # first check if the group exists
    group: RowProxy = await _get_user_group(conn, user_id, gid)
    check_group_permissions(group, user_id, gid, "write")
    # now check the user exists
    the_user: RowProxy = await _get_user_in_group_permissions(
        conn, gid, the_user_id_in_group
    )
    # modify the user access rights
    new_db_values = {"access_rights": access_rights}
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
    user = dict(the_user)
    user.update(**new_db_values)
    return convert_user_in_group_to_schema(user)


async def delete_user_in_group(
    conn: SAConnection, user_id: UserID, gid: GroupID, the_user_id_in_group: int
) -> None:
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


async def get_group_from_gid(conn: SAConnection, gid: GroupID) -> GroupAtDB | None:
    row: ResultProxy = await conn.execute(groups.select().where(groups.c.gid == gid))
    result = await row.first()
    if result:
        return GroupAtDB.model_validate(result)
    return None
