import re
from copy import deepcopy

import sqlalchemy as sa
from aiohttp import web
from models_library.groups import (
    AccessRightsDict,
    Group,
    GroupInfoTuple,
    GroupMember,
    GroupsByTypeTuple,
    OrganizationCreate,
    OrganizationUpdate,
)
from models_library.users import GroupID, UserID
from simcore_postgres_database.errors import UniqueViolation
from simcore_postgres_database.utils_products import execute_get_or_create_product_group
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine.row import Row
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.models import GroupType, groups, user_to_groups, users
from ..db.plugin import get_asyncpg_engine
from ..users.exceptions import UserNotFoundError
from .exceptions import (
    GroupNotFoundError,
    UserAlreadyInGroupError,
    UserInGroupNotFoundError,
    UserInsufficientRightsError,
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

_GROUP_COLUMNS = (
    groups.c.gid,
    groups.c.name,
    groups.c.description,
    groups.c.thumbnail,
    groups.c.type,
    groups.c.inclusion_rules,
    # NOTE: drops timestamps
)


def _row_to_model(group: Row) -> Group:
    return Group(
        gid=group.gid,
        name=group.name,
        description=group.description,
        thumbnail=group.thumbnail,
        group_type=group.type,
        inclusion_rules=group.inclusion_rules,
    )


def _to_group_info_tuple(group: Row) -> GroupInfoTuple:
    return (
        _row_to_model(group),
        AccessRightsDict(
            read=group.access_rights["read"],
            write=group.access_rights["write"],
            delete=group.access_rights["delete"],
        ),
    )


def _check_group_permissions(
    group: Row, user_id: int, gid: int, permission: str
) -> None:
    if not group.access_rights[permission]:
        raise UserInsufficientRightsError(
            user_id=user_id, gid=gid, permission=permission
        )


async def _get_group_and_access_rights_or_raise(
    conn: AsyncConnection,
    *,
    user_id: UserID,
    gid: GroupID,
) -> Row:
    result = await conn.stream(
        sa.select(
            *_GROUP_COLUMNS,
            user_to_groups.c.access_rights,
        )
        .select_from(user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid))
        .where((user_to_groups.c.uid == user_id) & (user_to_groups.c.gid == gid))
    )
    row = await result.fetchone()
    if not row:
        raise GroupNotFoundError(gid=gid)
    return row


#
# GROUPS
#


async def get_group_from_gid(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    group_id: GroupID,
) -> Group | None:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        row = await conn.stream(groups.select().where(groups.c.gid == group_id))
        result = await row.first()
        if result:
            return Group.model_validate(result)
        return None


#
# USER's GROUPS
#


async def get_all_user_groups_with_read_access(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
) -> GroupsByTypeTuple:

    """
    Returns the user primary group, standard groups and the all group
    """
    primary_group: GroupInfoTuple | None = None
    standard_groups: list[GroupInfoTuple] = []
    everyone_group: GroupInfoTuple | None = None

    query = (
        sa.select(groups, user_to_groups.c.access_rights)
        .select_from(
            user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid),
        )
        .where(user_to_groups.c.uid == user_id)
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(query)
        async for row in result:
            if row.type == GroupType.EVERYONE:
                assert row.access_rights["read"]  # nosec
                everyone_group = _to_group_info_tuple(row)

            elif row.type == GroupType.PRIMARY:
                assert row.access_rights["read"]  # nosec
                primary_group = _to_group_info_tuple(row)

            else:
                assert row.type == GroupType.STANDARD  # nosec
                # only add if user has read access
                if row.access_rights["read"]:
                    standard_groups.append(_to_group_info_tuple(row))

        return GroupsByTypeTuple(
            primary=primary_group, standard=standard_groups, everyone=everyone_group
        )


async def get_all_user_groups(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
) -> list[Group]:
    """
    Returns all user's groups
    """
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            sa.select(_GROUP_COLUMNS)
            .select_from(
                user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid),
            )
            .where(user_to_groups.c.uid == user_id)
        )
        return [Group.model_validate(row) async for row in result]


async def get_user_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    group_9d: GroupID,
) -> tuple[Group, AccessRightsDict]:
    """
    Gets group gid if user associated to it and has read access

    raises GroupNotFoundError
    raises UserInsufficientRightsError
    """
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        row = await _get_group_and_access_rights_or_raise(
            conn, user_id=user_id, gid=group_9d
        )
        _check_group_permissions(row, user_id, group_9d, "read")

        group, access_rights = _to_group_info_tuple(row)
        return group, access_rights


async def get_product_group_for_user(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_gid: GroupID,
) -> tuple[Group, AccessRightsDict]:
    """
    Returns product's group if user belongs to it, otherwise it
    raises GroupNotFoundError
    """
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        row = await _get_group_and_access_rights_or_raise(
            conn, user_id=user_id, gid=product_gid
        )
        group, access_rights = _to_group_info_tuple(row)
        return group, access_rights


assert set(OrganizationCreate.model_fields).issubset({c.name for c in groups.columns})


async def create_user_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    create: OrganizationCreate,
) -> tuple[Group, AccessRightsDict]:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        user = await conn.scalar(
            sa.select(users.c.primary_gid).where(users.c.id == user_id)
        )
        if not user:
            raise UserNotFoundError(uid=user_id)

        result = await conn.stream(
            # pylint: disable=no-value-for-parameter
            groups.insert()
            .values(**create.model_dump(mode="json", exclude_unset=True))
            .returning(*_GROUP_COLUMNS)
        )
        row = await result.fetchone()
        assert row  # nosec

        await conn.execute(
            # pylint: disable=no-value-for-parameter
            user_to_groups.insert().values(
                uid=user_id,
                gid=row.gid,
                access_rights=_DEFAULT_GROUP_OWNER_ACCESS_RIGHTS,
            )
        )

        group = _row_to_model(row)
        return group, deepcopy(_DEFAULT_GROUP_OWNER_ACCESS_RIGHTS)


assert set(OrganizationUpdate.model_fields).issubset({c.name for c in groups.columns})


async def update_user_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    group_id: GroupID,
    update: OrganizationUpdate,
) -> tuple[Group, AccessRightsDict]:

    values = update.model_dump(mode="json", exclude_unset=True)

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        row = await _get_group_and_access_rights_or_raise(
            conn, user_id=user_id, gid=group_id
        )
        assert row.gid == group_id  # nosec
        _check_group_permissions(row, user_id, group_id, "write")
        access_rights = AccessRightsDict(**row.access_rights)  # type: ignore[typeddict-item]

        result = await conn.stream(
            # pylint: disable=no-value-for-parameter
            groups.update()
            .values(**values)
            .where(groups.c.gid == row.gid)
            .returning(*_GROUP_COLUMNS)
        )
        row = await result.fetchone()
        assert row  # nosec

        group = _row_to_model(row)
        return group, access_rights


async def delete_user_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    group_id: GroupID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        group = await _get_group_and_access_rights_or_raise(
            conn, user_id=user_id, gid=group_id
        )
        _check_group_permissions(group, user_id, group_id, "delete")

        await conn.execute(
            # pylint: disable=no-value-for-parameter
            groups.delete().where(groups.c.gid == group.gid)
        )


#
# USERS
#


async def get_user_from_email(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    caller_user_id: UserID,
    email: str,
) -> Row:
    """
    Raises:
        UserNotFoundError: if not found or privacy hides email

    """
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            sa.select(users.c.id).where(
                (users.c.email == email)
                & (
                    users.c.privacy_hide_email.is_(False)
                    | (users.c.id == caller_user_id)
                )
            )
        )
        user = await result.fetchone()
        if not user:
            raise UserNotFoundError(email=email)
        return user


#
# GROUP MEMBERS - CRUD
#


def _group_user_cols(caller_user_id: int):
    return (
        users.c.id,
        users.c.name,
        # privacy settings
        sa.case(
            (
                users.c.privacy_hide_email.is_(True) & (users.c.id != caller_user_id),
                None,
            ),
            else_=users.c.email,
        ).label("email"),
        sa.case(
            (
                users.c.privacy_hide_fullname.is_(True)
                & (users.c.id != caller_user_id),
                None,
            ),
            else_=users.c.first_name,
        ).label("first_name"),
        sa.case(
            (
                users.c.privacy_hide_fullname.is_(True)
                & (users.c.id != caller_user_id),
                None,
            ),
            else_=users.c.last_name,
        ).label("last_name"),
        users.c.primary_gid,
    )


async def _get_user_in_group(
    conn: AsyncConnection, *, caller_user_id, group_id: GroupID, user_id: int
) -> Row:
    # now get the user
    result = await conn.stream(
        sa.select(*_group_user_cols(caller_user_id), user_to_groups.c.access_rights)
        .select_from(
            users.join(user_to_groups, users.c.id == user_to_groups.c.uid),
        )
        .where(and_(user_to_groups.c.gid == group_id, users.c.id == user_id))
    )
    row = await result.fetchone()
    if not row:
        raise UserInGroupNotFoundError(uid=user_id, gid=group_id)
    return row


async def list_users_in_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    group_id: GroupID,
) -> list[GroupMember]:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        # first check if the group exists
        group = await _get_group_and_access_rights_or_raise(
            conn, user_id=user_id, gid=group_id
        )
        _check_group_permissions(group, user_id, group_id, "read")

        # now get the list
        query = (
            sa.select(
                *_group_user_cols(user_id),
                user_to_groups.c.access_rights,
            )
            .select_from(users.join(user_to_groups))
            .where(user_to_groups.c.gid == group_id)
        )

        result = await conn.stream(query)
        return [GroupMember.model_validate(row) async for row in result]


async def get_user_in_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    group_id: GroupID,
    the_user_id_in_group: int,
) -> GroupMember:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        # first check if the group exists
        group = await _get_group_and_access_rights_or_raise(
            conn, user_id=user_id, gid=group_id
        )
        _check_group_permissions(group, user_id, group_id, "read")

        # get the user with its permissions
        the_user = await _get_user_in_group(
            conn,
            caller_user_id=user_id,
            group_id=group_id,
            user_id=the_user_id_in_group,
        )
        return GroupMember.model_validate(the_user)


async def update_user_in_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    group_id: GroupID,
    the_user_id_in_group: UserID,
    access_rights: AccessRightsDict,
) -> GroupMember:
    if not access_rights:
        msg = f"Cannot update empty {access_rights}"
        raise ValueError(msg)

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:

        # first check if the group exists
        group = await _get_group_and_access_rights_or_raise(
            conn, user_id=user_id, gid=group_id
        )
        _check_group_permissions(group, user_id, group_id, "write")

        # now check the user exists
        the_user = await _get_user_in_group(
            conn,
            caller_user_id=user_id,
            group_id=group_id,
            user_id=the_user_id_in_group,
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
                    user_to_groups.c.gid == group_id,
                )
            )
        )
        user = dict(the_user)
        user.update(**new_db_values)
        return GroupMember.model_validate(user)


async def delete_user_from_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    group_id: GroupID,
    the_user_id_in_group: UserID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        # first check if the group exists
        group = await _get_group_and_access_rights_or_raise(
            conn, user_id=user_id, gid=group_id
        )
        _check_group_permissions(group, user_id, group_id, "write")

        # check the user exists
        await _get_user_in_group(
            conn,
            caller_user_id=user_id,
            group_id=group_id,
            user_id=the_user_id_in_group,
        )

        # delete him/her
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            user_to_groups.delete().where(
                and_(
                    user_to_groups.c.uid == the_user_id_in_group,
                    user_to_groups.c.gid == group_id,
                )
            )
        )


#
# GROUP MEMBERS - CUSTOM
#


async def is_user_by_email_in_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    email: str,
    group_id: GroupID,
) -> bool:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        user_id = await conn.scalar(
            sa.select(users.c.id)
            .select_from(
                sa.join(user_to_groups, users, user_to_groups.c.uid == users.c.id)
            )
            .where((users.c.email == email) & (user_to_groups.c.gid == group_id))
        )
        return user_id is not None


async def add_new_user_in_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    group_id: GroupID,
    new_user_id: UserID,
    access_rights: AccessRightsDict | None = None,
) -> None:
    """
    adds new_user (either by id or email) in group (with gid) owned by user_id
    """
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        # first check if the group exists
        group = await _get_group_and_access_rights_or_raise(
            conn, user_id=user_id, gid=group_id
        )
        _check_group_permissions(group, user_id, group_id, "write")

        # now check the new user exists
        users_count = await conn.scalar(
            sa.select(sa.func.count()).where(users.c.id == new_user_id)
        )
        if not users_count:
            assert new_user_id is not None  # nosec
            raise UserInGroupNotFoundError(uid=new_user_id, gid=group_id)

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
                uid=new_user_id,
                gid=group_id,
                user_id=user_id,
                access_rights=access_rights,
            ) from exc


async def auto_add_user_to_groups(
    app: web.Application, connection: AsyncConnection | None = None, *, user: dict
) -> None:

    user_id: UserID = user["id"]

    # auto add user to the groups with the right rules
    # get the groups where there are inclusion rules and see if they apply
    query = sa.select(groups).where(groups.c.inclusion_rules != {})
    possible_group_ids = set()

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(query)
        async for row in result:
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
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: str,
) -> GroupID:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        product_group_id: GroupID = await execute_get_or_create_product_group(
            conn, product_name
        )

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
