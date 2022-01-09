"""
    This should be the interface other modules should use to get
    information from user module

"""

import logging
from collections import deque
from typing import Any, Dict, List, Tuple, TypedDict

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.engine import Engine
from aiopg.sa.result import RowProxy
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.login.cfg import get_storage
from sqlalchemy import and_, literal_column

from .db_models import GroupType, groups, tokens, user_to_groups, users
from .groups_utils import convert_groups_db_to_schema
from .login.storage import AsyncpgStorage
from .security_api import clean_auth_policy_cache
from .users_exceptions import UserNotFoundError
from .users_utils import convert_user_db_to_schema

logger = logging.getLogger(__name__)


# USERS  API ----------------------------------------------------------------------------


async def get_user_profile(app: web.Application, user_id: int) -> Dict[str, Any]:
    engine: Engine = app[APP_DB_ENGINE_KEY]
    user_profile: Dict[str, Any] = {}
    user_primary_group = all_group = {}
    user_standard_groups = []

    async with engine.acquire() as conn:
        async for row in conn.execute(
            sa.select(
                [
                    users,
                    groups,
                    user_to_groups.c.access_rights,
                ],
                use_labels=True,
            )
            .select_from(
                users.join(
                    user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid),
                    users.c.id == user_to_groups.c.uid,
                )
            )
            .where(users.c.id == user_id)
            .order_by(sa.asc(groups.c.name))
        ):
            user_profile.update(convert_user_db_to_schema(row, prefix="users_"))
            if row["groups_type"] == GroupType.EVERYONE:
                all_group = convert_groups_db_to_schema(
                    row,
                    prefix="groups_",
                    accessRights=row["user_to_groups_access_rights"],
                )
            elif row["groups_type"] == GroupType.PRIMARY:
                user_primary_group = convert_groups_db_to_schema(
                    row,
                    prefix="groups_",
                    accessRights=row["user_to_groups_access_rights"],
                )
            else:
                user_standard_groups.append(
                    convert_groups_db_to_schema(
                        row,
                        prefix="groups_",
                        accessRights=row["user_to_groups_access_rights"],
                    )
                )
    if not user_profile:
        raise UserNotFoundError(uid=user_id)

    user_profile["groups"] = {
        "me": user_primary_group,
        "organizations": user_standard_groups,
        "all": all_group,
    }
    return user_profile


async def update_user_profile(
    app: web.Application, user_id: int, profile: Dict
) -> None:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        default_name = await conn.scalar(
            sa.select([users.c.name]).where(users.c.id == user_id)
        )
        parts = default_name.split(".") + [""]
        name = (
            profile.get("first_name", parts[0])
            + "."
            + profile.get("last_name", parts[1])
        )
        resp = await conn.execute(
            # pylint: disable=no-value-for-parameter
            users.update()
            .where(users.c.id == user_id)
            .values(name=name)
        )
        assert resp.rowcount == 1  # nosec


async def is_user_guest(app: web.Application, user_id: int) -> bool:
    """Returns True if the user exists and is a GUEST"""
    db = get_storage(app)
    user = await db.get_user({"id": user_id})
    if not user:
        logger.warning("Could not find user with id '%s'", user_id)
        return False

    return bool(UserRole(user["role"]) == UserRole.GUEST)


async def get_guest_user_ids_and_names(app: web.Application) -> List[Tuple[int, str]]:
    engine = app[APP_DB_ENGINE_KEY]
    result = deque()
    async with engine.acquire() as conn:
        async for row in conn.execute(
            sa.select([users.c.id, users.c.name]).where(users.c.role == UserRole.GUEST)
        ):
            result.append(row.as_tuple())
        return list(result)


async def delete_user(app: web.Application, user_id: int) -> None:
    """Deletes a user from the database if the user exists"""
    # FIXME: user cannot be deleted without deleting first all ist project
    # otherwise this function will raise asyncpg.exceptions.ForeignKeyViolationError
    # Consider "marking" users as deleted and havning a background job that
    # cleans it up
    db: AsyncpgStorage = get_storage(app)
    user = await db.get_user({"id": user_id})
    if not user:
        logger.warning(
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


async def get_user_name(app: web.Application, user_id: int) -> UserNameDict:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        user_name = await conn.scalar(
            sa.select([users.c.name]).where(users.c.id == user_id)
        )
        if not user_name:
            raise UserNotFoundError(uid=user_id)
        parts = user_name.split(".") + [""]
        return UserNameDict(first_name=parts[0], last_name=parts[1])


async def get_user(app: web.Application, user_id: int) -> Dict:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        result = await conn.execute(sa.select([users]).where(users.c.id == user_id))
        row: RowProxy = await result.fetchone()
        if not row:
            raise UserNotFoundError(uid=user_id)
        return dict(row)


async def get_user_id_from_gid(app: web.Application, primary_gid: int) -> int:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        return await conn.scalar(
            sa.select([users.c.id]).where(users.c.primary_gid == primary_gid)
        )


# TOKEN  API ----------------------------------------------------------------------------


async def create_token(
    app: web.Application, user_id: int, token_data: Dict[str, str]
) -> Dict[str, str]:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            tokens.insert().values(
                user_id=user_id,
                token_service=token_data["service"],
                token_data=token_data,
            )
        )
        return token_data


async def list_tokens(app: web.Application, user_id: int) -> List[Dict[str, str]]:
    engine = app[APP_DB_ENGINE_KEY]
    user_tokens = []
    async with engine.acquire() as conn:
        async for row in conn.execute(
            sa.select([tokens.c.token_data]).where(tokens.c.user_id == user_id)
        ):
            user_tokens.append(row["token_data"])
        return user_tokens


async def get_token(
    app: web.Application, user_id: int, service_id: str
) -> Dict[str, str]:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        result = await conn.execute(
            sa.select([tokens.c.token_data]).where(
                and_(tokens.c.user_id == user_id, tokens.c.token_service == service_id)
            )
        )
        row: RowProxy = await result.first()
        return dict(row["token_data"])


async def update_token(
    app: web.Application, user_id: int, service_id: str, token_data: Dict[str, str]
) -> Dict[str, str]:
    engine = app[APP_DB_ENGINE_KEY]
    # TODO: optimize to a single call?
    async with engine.acquire() as conn:
        result = await conn.execute(
            sa.select([tokens.c.token_data, tokens.c.token_id]).where(
                and_(tokens.c.user_id == user_id, tokens.c.token_service == service_id)
            )
        )
        row = await result.first()

        data = dict(row["token_data"])
        tid = row["token_id"]
        data.update(token_data)

        resp = await conn.execute(
            # pylint: disable=no-value-for-parameter
            tokens.update()
            .where(tokens.c.token_id == tid)
            .values(token_data=data)
            .returning(literal_column("*"))
        )
        assert resp.rowcount == 1  # nosec
        updated_token: RowProxy = await resp.fetchone()
        return dict(updated_token["token_data"])


async def delete_token(app: web.Application, user_id: int, service_id: str) -> None:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            tokens.delete().where(
                and_(tokens.c.user_id == user_id, tokens.c.token_service == service_id)
            )
        )
