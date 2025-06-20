import re
from copy import deepcopy
from typing import Literal

import sqlalchemy as sa
from aiohttp import web
from common_library.groups_enums import GroupType
from common_library.users_enums import UserRole
from models_library.basic_types import IDStr
from models_library.groups import (
    AccessRightsDict,
    Group,
    GroupID,
    GroupInfoTuple,
    GroupMember,
    GroupsByTypeTuple,
    StandardGroupCreate,
    StandardGroupUpdate,
)
from models_library.users import UserID
from simcore_postgres_database.aiopg_errors import UniqueViolation
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils_products import get_or_create_product_group
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from simcore_postgres_database.utils_users import is_public, visible_user_profile_cols
from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine.row import Row
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.models import groups, user_to_groups, users
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
    group: Row,
    caller_id: UserID,
    group_id: GroupID,
    permission: Literal["read", "write", "delete"],
) -> None:
    if not group.access_rights[permission]:
        raise UserInsufficientRightsError(
            user_id=caller_id, gid=group_id, permission=permission
        )


async def _get_group_and_access_rights_or_raise(
    conn: AsyncConnection,
    *,
    caller_id: UserID,
    group_id: GroupID,
    permission: Literal["read", "write", "delete"] | None,
) -> Row:
    result = await conn.execute(
        sa.select(
            *_GROUP_COLUMNS,
            user_to_groups.c.access_rights,
        )
        .select_from(groups.join(user_to_groups, user_to_groups.c.gid == groups.c.gid))
        .where((user_to_groups.c.uid == caller_id) & (user_to_groups.c.gid == group_id))
    )
    row = result.one_or_none()
    if not row:
        raise GroupNotFoundError(gid=group_id)

    if permission:
        _check_group_permissions(row, caller_id, group_id, permission)

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
        row = await conn.execute(
            sa.select(*_GROUP_COLUMNS).where(groups.c.gid == group_id)
        )
        result = row.first()
        if result:
            return Group.model_validate(result, from_attributes=True)
        return None


#
# USER's GROUPS
#


def _list_user_groups_with_read_access_query(*group_selection, user_id: UserID):
    return (
        sa.select(*group_selection, user_to_groups.c.access_rights)
        .select_from(
            user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid),
        )
        .where(
            (user_to_groups.c.uid == user_id)
            & (user_to_groups.c.access_rights["read"].astext == "true")
        )
    )


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

    query = _list_user_groups_with_read_access_query(groups, user_id=user_id)

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


async def get_ids_of_all_user_groups_with_read_access(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
) -> list[GroupID]:
    # thin version of `get_all_user_groups_with_read_access`

    query = _list_user_groups_with_read_access_query(groups.c.gid, user_id=user_id)

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(query)
        return [row.gid async for row in result]


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
            sa.select(*_GROUP_COLUMNS)
            .select_from(
                user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid),
            )
            .where(user_to_groups.c.uid == user_id)
        )
        return [Group.model_validate(row) async for row in result]


async def get_ids_of_all_user_groups(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
) -> list[GroupID]:
    # thin version of `get_all_user_groups`
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            sa.select(
                groups.c.gid,
            )
            .select_from(
                user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid),
            )
            .where(user_to_groups.c.uid == user_id)
        )
        return [row.gid async for row in result]


async def get_user_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    group_id: GroupID,
) -> tuple[Group, AccessRightsDict]:
    """
    Gets group gid if user associated to it and has read access

    raises GroupNotFoundError
    raises UserInsufficientRightsError
    """
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        row = await _get_group_and_access_rights_or_raise(
            conn, caller_id=user_id, group_id=group_id, permission="read"
        )
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
            conn,
            caller_id=user_id,
            group_id=product_gid,
            permission=None,
        )
        group, access_rights = _to_group_info_tuple(row)
        return group, access_rights


assert set(StandardGroupCreate.model_fields).issubset({c.name for c in groups.columns})


async def create_standard_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    create: StandardGroupCreate,
) -> tuple[Group, AccessRightsDict]:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        user = await conn.scalar(
            sa.select(
                users.c.primary_gid,
            ).where(users.c.id == user_id)
        )
        if not user:
            raise UserNotFoundError(user_id=user_id)

        result = await conn.stream(
            # pylint: disable=no-value-for-parameter
            groups.insert()
            .values(
                **create.model_dump(mode="json", exclude_unset=True),
                type=GroupType.STANDARD,
            )
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


assert set(StandardGroupUpdate.model_fields).issubset({c.name for c in groups.columns})


async def update_standard_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    group_id: GroupID,
    update: StandardGroupUpdate,
) -> tuple[Group, AccessRightsDict]:
    values = update.model_dump(mode="json", exclude_unset=True)

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        row = await _get_group_and_access_rights_or_raise(
            conn, caller_id=user_id, group_id=group_id, permission="write"
        )
        assert row.gid == group_id  # nosec
        # NOTE: update does not include access-rights
        access_rights = AccessRightsDict(**row.access_rights)  # type: ignore[typeddict-item]

        result = await conn.execute(
            # pylint: disable=no-value-for-parameter
            groups.update()
            .values(**values)
            .where((groups.c.gid == group_id) & (groups.c.type == GroupType.STANDARD))
            .returning(*_GROUP_COLUMNS)
        )
        row = result.one()

        group = _row_to_model(row)
        return group, access_rights


async def delete_standard_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    group_id: GroupID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await _get_group_and_access_rights_or_raise(
            conn, caller_id=user_id, group_id=group_id, permission="delete"
        )

        await conn.execute(
            # pylint: disable=no-value-for-parameter
            groups.delete().where(
                (groups.c.gid == group_id) & (groups.c.type == GroupType.STANDARD)
            )
        )


#
# USERS
#


async def get_user_from_email(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    caller_id: UserID,
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
                & is_public(users.c.privacy_hide_email, caller_id=caller_id)
            )
        )
        user = await result.fetchone()
        if not user:
            raise UserNotFoundError(email=email)
        return user


#
# GROUP MEMBERS - CRUD
#


def _group_user_cols(caller_id: UserID):
    return (
        users.c.id,
        *visible_user_profile_cols(caller_id, username_label="name"),
        users.c.primary_gid,
    )


async def _get_user_in_group_or_raise(
    conn: AsyncConnection, *, caller_id: UserID, group_id: GroupID, user_id: UserID
) -> Row:
    # NOTE: that the caller_id might be different that the target user_id
    result = await conn.stream(
        sa.select(
            *_group_user_cols(caller_id),
            user_to_groups.c.access_rights,
        )
        .select_from(
            users.join(user_to_groups, users.c.id == user_to_groups.c.uid),
        )
        .where((user_to_groups.c.gid == group_id) & (users.c.id == user_id))
    )
    row = await result.fetchone()
    if not row:
        raise UserInGroupNotFoundError(uid=user_id, gid=group_id)
    return row


async def list_users_in_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    caller_id: UserID,
    group_id: GroupID,
) -> list[GroupMember]:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        # GET GROUP & caller access-rights (if non PRIMARY)
        query = (
            sa.select(
                *_GROUP_COLUMNS,
                user_to_groups.c.access_rights,
            )
            .select_from(
                groups.join(
                    user_to_groups, user_to_groups.c.gid == groups.c.gid, isouter=True
                ).join(users, users.c.id == user_to_groups.c.uid)
            )
            .where(
                (user_to_groups.c.gid == group_id)
                & (
                    (user_to_groups.c.uid == caller_id)
                    | (
                        (groups.c.type == GroupType.PRIMARY)
                        & users.c.role.in_([r for r in UserRole if r > UserRole.GUEST])
                    )
                )
            )
        )

        result = await conn.execute(query)
        group_row = result.first()
        if not group_row:
            raise GroupNotFoundError(gid=group_id)

        # Drop access-rights if primary group
        if group_row.type == GroupType.PRIMARY:
            query = sa.select(
                *_group_user_cols(caller_id),
            )
        else:
            _check_group_permissions(
                group_row, caller_id=caller_id, group_id=group_id, permission="read"
            )
            query = sa.select(
                *_group_user_cols(caller_id),
                user_to_groups.c.access_rights,
            )

        # GET users
        query = query.select_from(users.join(user_to_groups, isouter=True)).where(
            user_to_groups.c.gid == group_id
        )

        aresult = await conn.stream(query)
        return [
            GroupMember.model_validate(row, from_attributes=True)
            async for row in aresult
        ]


async def get_user_in_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    caller_id: UserID,
    group_id: GroupID,
    the_user_id_in_group: int,
) -> GroupMember:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        # first check if the group exists
        await _get_group_and_access_rights_or_raise(
            conn, caller_id=caller_id, group_id=group_id, permission="read"
        )

        # get the user with its permissions
        the_user = await _get_user_in_group_or_raise(
            conn,
            caller_id=caller_id,
            group_id=group_id,
            user_id=the_user_id_in_group,
        )
        return GroupMember.model_validate(the_user)


async def update_user_in_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    caller_id: UserID,
    group_id: GroupID,
    the_user_id_in_group: UserID,
    access_rights: AccessRightsDict,
) -> GroupMember:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        # first check if the group exists
        await _get_group_and_access_rights_or_raise(
            conn, caller_id=caller_id, group_id=group_id, permission="write"
        )

        # now check the user exists
        the_user = await _get_user_in_group_or_raise(
            conn,
            caller_id=caller_id,
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
        user = the_user._asdict()
        user.update(**new_db_values)
        return GroupMember.model_validate(user)


async def delete_user_from_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    caller_id: UserID,
    group_id: GroupID,
    the_user_id_in_group: UserID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        # first check if the group exists
        await _get_group_and_access_rights_or_raise(
            conn, caller_id=caller_id, group_id=group_id, permission="write"
        )

        # check the user exists
        await _get_user_in_group_or_raise(
            conn,
            caller_id=caller_id,
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
    caller_id: UserID,
    group_id: GroupID,
    # either user_id or user_name
    new_user_id: UserID | None = None,
    new_user_name: IDStr | None = None,
    access_rights: AccessRightsDict | None = None,
) -> None:
    """
    adds new_user (either by id or email) in group (with gid) owned by user_id
    """
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        # first check if the group exists
        await _get_group_and_access_rights_or_raise(
            conn, caller_id=caller_id, group_id=group_id, permission="write"
        )

        query = sa.select(users.c.id)
        if new_user_id is not None:
            query = query.where(users.c.id == new_user_id)
        elif new_user_name is not None:
            query = query.where(users.c.name == new_user_name)
        else:
            msg = "Expected either user-name or user-ID but none was provided"
            raise ValueError(msg)

        # now check the new user exists
        new_user_id = await conn.scalar(query)
        if not new_user_id:
            raise UserInGroupNotFoundError(uid=new_user_id, gid=group_id)

        # add the new user to the group now
        user_access_rights = _DEFAULT_GROUP_READ_ACCESS_RIGHTS
        if access_rights:
            user_access_rights.update(access_rights)

        try:
            await conn.execute(
                # pylint: disable=no-value-for-parameter
                user_to_groups.insert().values(
                    uid=new_user_id, gid=group_id, access_rights=user_access_rights
                )
            )
        except UniqueViolation as exc:
            raise UserAlreadyInGroupError(
                uid=new_user_id,
                gid=group_id,
                user_id=caller_id,
                access_rights=access_rights,
            ) from exc


async def auto_add_user_to_groups(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user: dict,
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
        product_group_id: GroupID = await get_or_create_product_group(
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
            .on_conflict_do_nothing()  # in case the user was already added to this group
        )
        return product_group_id
