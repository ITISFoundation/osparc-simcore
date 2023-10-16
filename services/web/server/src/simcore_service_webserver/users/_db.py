import contextlib
from typing import NamedTuple

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from models_library.users import GroupID, UserID
from simcore_postgres_database.models.users import UserStatus, users
from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraPropertiesNotFoundError,
    GroupExtraPropertiesRepo,
)
from simcore_service_webserver.users.exceptions import UserNotFoundError

from ..db.models import user_to_groups
from ..db.plugin import get_database_engine
from .schemas import Permission


async def do_update_expired_users(conn: SAConnection) -> list[UserID]:
    result: ResultProxy = await conn.execute(
        users.update()
        .values(status=UserStatus.EXPIRED)
        .where(
            (users.c.expires_at.is_not(None))
            & (users.c.status == UserStatus.ACTIVE)
            & (users.c.expires_at < sa.sql.func.now())
        )
        .returning(users.c.id)
    )
    if rows := await result.fetchall():
        return [r.id for r in rows]
    return []


async def get_users_ids_in_group(conn: SAConnection, gid: GroupID) -> set[UserID]:
    result: set[UserID] = set()
    query_result = await conn.execute(
        sa.select(user_to_groups.c.uid).where(user_to_groups.c.gid == gid)
    )
    async for entry in query_result:
        result.add(entry[0])
    return result


async def list_user_permissions(
    app: web.Application, *, user_id: UserID, product_name: str
) -> list[Permission]:
    override_services_specifications = Permission(
        name="override_services_specifications",
        allowed=False,
    )
    with contextlib.suppress(GroupExtraPropertiesNotFoundError):
        async with get_database_engine(app).acquire() as conn:
            user_group_extra_properties = (
                await GroupExtraPropertiesRepo.get_aggregated_properties_for_user(
                    conn, user_id=user_id, product_name=product_name
                )
            )
        override_services_specifications.allowed = (
            user_group_extra_properties.override_services_specifications
        )

    return [override_services_specifications]


class UserNameAndEmailTuple(NamedTuple):
    name: str
    email: str


async def get_username_and_email(
    connection: SAConnection, user_id: UserID
) -> UserNameAndEmailTuple:
    row: RowProxy | None = await (
        await connection.execute(
            sa.select(users.c.name, users.c.email).where(users.c.id == user_id)
        )
    ).first()
    if row is None:
        raise UserNotFoundError(uid=user_id)
    assert row.name  # nosec
    assert row.email  # nosec
    return UserNameAndEmailTuple(name=row.name, email=row.email)


class UserEmailAndPassHashTuple(NamedTuple):
    email: str
    password_hash: str


async def get_email_and_password_hash(
    app: web.Application, *, user_id: UserID
) -> UserEmailAndPassHashTuple:
    async with get_database_engine(app).acquire() as conn:
        row: RowProxy | None = await (
            await conn.execute(
                sa.select(users.c.password_hash, users.c.email).where(
                    users.c.id == user_id
                )
            )
        ).first()
        if row is None:
            raise UserNotFoundError(uid=user_id)
        return UserEmailAndPassHashTuple(
            email=row.email, password_hash=row.password_hash
        )


async def mark_user_as_deleted(app: web.Application, *, user_id: UserID):
    async with get_database_engine(app).acquire() as conn:
        await conn.execute(
            users.update()
            .values(status=UserStatus.DELETED)
            .where(users.c.user_id == user_id)
        )
