"""
    This should be the interface other modules should use to get
    information from user module

"""

import logging
from collections import deque
from typing import Any, TypedDict

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.engine import Engine
from aiopg.sa.result import RowProxy
from models_library.users import GroupID, UserID
from simcore_postgres_database.models.users import UserNameConverter, UserRole

from ..db.models import GroupType, groups, user_to_groups, users
from ..db.plugin import get_database_engine
from ..groups.models import convert_groups_db_to_schema
from ..login.storage import AsyncpgStorage, get_plugin_storage
from ..security.api import clean_auth_policy_cache
from . import _db
from ._db import list_user_permissions as db_list_of_permissions
from .exceptions import UserNotFoundError
from .schemas import Permission, ProfileGet, ProfileUpdate, convert_user_db_to_schema

_logger = logging.getLogger(__name__)


def _parse_as_user(user_id: Any) -> UserID:
    # analogous to pydantic.parse_obj_as(PositiveInt, user_id) but lighter and
    # raise UserNotFoundError instead of ValidationError
    try:
        user_id = int(user_id)
    except ValueError as err:
        raise UserNotFoundError(uid=user_id) from err

    if user_id <= 0:
        raise UserNotFoundError(uid=user_id)
    return user_id


async def get_user_profile(app: web.Application, user_id: UserID) -> ProfileGet:
    """
    :raises UserNotFoundError:
    """

    engine = get_database_engine(app)
    user_profile: dict[str, Any] = {}
    user_primary_group = all_group = {}
    user_standard_groups = []
    user_id = _parse_as_user(user_id)

    async with engine.acquire() as conn:
        async for row in conn.execute(
            sa.select(users, groups, user_to_groups.c.access_rights)
            .select_from(
                sa.join(
                    users,
                    sa.join(
                        user_to_groups, groups, user_to_groups.c.gid == groups.c.gid
                    ),
                    users.c.id == user_to_groups.c.uid,
                )
            )
            .where(users.c.id == user_id)
            .order_by(sa.asc(groups.c.name))
            .set_label_style(sa.LABEL_STYLE_TABLENAME_PLUS_COL)
        ):
            row_dict = dict(row.items())
            user_profile.update(convert_user_db_to_schema(row_dict, prefix="users_"))
            if row_dict["groups_type"] == GroupType.EVERYONE:
                all_group = convert_groups_db_to_schema(
                    row_dict,
                    prefix="groups_",
                    accessRights=row_dict["user_to_groups_access_rights"],
                )
            elif row_dict["groups_type"] == GroupType.PRIMARY:
                user_primary_group = convert_groups_db_to_schema(
                    row_dict,
                    prefix="groups_",
                    accessRights=row_dict["user_to_groups_access_rights"],
                )
            else:
                user_standard_groups.append(
                    convert_groups_db_to_schema(
                        row_dict,
                        prefix="groups_",
                        accessRights=row_dict["user_to_groups_access_rights"],
                    )
                )
    if not user_profile:
        raise UserNotFoundError(uid=user_id)

    user_profile["groups"] = {
        "me": user_primary_group,
        "organizations": user_standard_groups,
        "all": all_group,
    }

    if expires_at := user_profile.get("expires_at"):
        user_profile["expiration_date"] = expires_at.date()

    return ProfileGet.parse_obj(user_profile)


async def update_user_profile(
    app: web.Application, user_id: UserID, profile_update: ProfileUpdate
) -> None:
    """
    :raises UserNotFoundError:
    """

    engine = get_database_engine(app)
    user_id = _parse_as_user(user_id)

    async with engine.acquire() as conn:
        first_name = profile_update.first_name
        last_name = profile_update.last_name
        if not first_name or not last_name:
            name = await conn.scalar(
                sa.select(users.c.name).where(users.c.id == user_id)
            )
            try:
                first_name, last_name = name.rsplit(".", maxsplit=2)
            except ValueError:
                first_name = name

        # update name
        name = UserNameConverter.get_name(
            first_name=profile_update.first_name or first_name,
            last_name=profile_update.last_name or last_name,
        )
        resp = await conn.execute(
            # pylint: disable=no-value-for-parameter
            users.update()
            .where(users.c.id == user_id)
            .values(name=name)
        )
        assert resp.rowcount == 1  # nosec


async def get_user_role(app: web.Application, user_id: UserID) -> UserRole:
    """
    :raises UserNotFoundError:
    """
    user_id = _parse_as_user(user_id)

    engine = get_database_engine(app)
    async with engine.acquire() as conn:
        user_role: RowProxy | None = await conn.scalar(
            sa.select(users.c.role).where(users.c.id == user_id)
        )
        if user_role is None:
            raise UserNotFoundError(uid=user_id)
        return UserRole(user_role)


async def get_guest_user_ids_and_names(app: web.Application) -> list[tuple[int, str]]:
    engine = get_database_engine(app)
    result: deque = deque()
    async with engine.acquire() as conn:
        async for row in conn.execute(
            sa.select(users.c.id, users.c.name).where(users.c.role == UserRole.GUEST)
        ):
            result.append(row.as_tuple())
        return list(result)


async def delete_user_without_projects(app: web.Application, user_id: UserID) -> None:
    """Deletes a user from the database if the user exists"""
    # WARNING: user cannot be deleted without deleting first all ist project
    # otherwise this function will raise asyncpg.exceptions.ForeignKeyViolationError
    # Consider "marking" users as deleted and havning a background job that
    # cleans it up
    db: AsyncpgStorage = get_plugin_storage(app)
    user = await db.get_user({"id": user_id})
    if not user:
        _logger.warning(
            "User with id '%s' could not be deleted because it does not exist", user_id
        )
        return

    await db.delete_user(user)

    # This user might be cached in the auth. If so, any request
    # with this user-id will get thru producing unexpected side-effects
    clean_auth_policy_cache(app)


class UserNameDict(TypedDict):
    first_name: str
    last_name: str


async def get_user_name(app: web.Application, user_id: UserID) -> UserNameDict:
    """
    :raises UserNotFoundError:
    """
    engine = get_database_engine(app)
    user_id = _parse_as_user(user_id)
    async with engine.acquire() as conn:
        user_name = await conn.scalar(
            sa.select(users.c.name).where(users.c.id == user_id)
        )
        if not user_name:
            raise UserNotFoundError(uid=user_id)

        full_name = UserNameConverter.get_full_name(user_name)
        return UserNameDict(
            first_name=full_name.first_name,
            last_name=full_name.last_name,
        )


async def get_user(app: web.Application, user_id: UserID) -> dict:
    """
    :raises UserNotFoundError:
    """
    engine = get_database_engine(app)
    user_id = _parse_as_user(user_id)
    async with engine.acquire() as conn:
        result = await conn.execute(sa.select(users).where(users.c.id == user_id))
        row: RowProxy = await result.fetchone()
        if not row:
            raise UserNotFoundError(uid=user_id)
        return dict(row)


async def get_user_id_from_gid(app: web.Application, primary_gid: int) -> UserID:
    engine = get_database_engine(app)
    async with engine.acquire() as conn:
        user_id: UserID = await conn.scalar(
            sa.select(users.c.id).where(users.c.primary_gid == primary_gid)
        )
        return user_id


async def get_users_in_group(app: web.Application, gid: GroupID) -> set[UserID]:
    engine = get_database_engine(app)
    async with engine.acquire() as conn:
        return await _db.get_users_ids_in_group(conn, gid)


async def update_expired_users(engine: Engine) -> list[UserID]:
    async with engine.acquire() as conn:
        return await _db.do_update_expired_users(conn)


async def list_user_permissions(
    app: web.Application, user_id: UserID, product_name: str
) -> list[Permission]:
    list_of_permissions = await db_list_of_permissions(
        app, user_id=user_id, product_name=product_name
    )
    return list_of_permissions
