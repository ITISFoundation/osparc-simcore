import contextlib

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from models_library.users import GroupID, UserID
from simcore_postgres_database.models.users import UserStatus, users
from simcore_postgres_database.models.users_details import invited_users
from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraPropertiesNotFoundError,
    GroupExtraPropertiesRepo,
)
from simcore_service_webserver.users.exceptions import UserNotFoundError

from ..db.models import user_to_groups
from ..db.plugin import get_database_engine
from .schemas import Permission

_ALL = None


async def get_user_or_raise(
    engine: Engine, *, user_id: UserID, return_column_names: list[str] | None = _ALL
) -> RowProxy:
    if return_column_names == _ALL:
        return_column_names = list(users.columns.keys())

    assert return_column_names is not None  # nosec
    assert set(return_column_names).issubset(users.columns.keys())  # nosec

    async with engine.acquire() as conn:
        row: RowProxy | None = await (
            await conn.execute(
                sa.select(*(users.columns[name] for name in return_column_names)).where(
                    users.c.id == user_id
                )
            )
        ).first()
        if row is None:
            raise UserNotFoundError(uid=user_id)
        return row


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


async def update_user_status(
    engine: Engine, *, user_id: UserID, new_status: UserStatus
):
    async with engine.acquire() as conn:
        await conn.execute(
            users.update().values(status=new_status).where(users.c.id == user_id)
        )


async def search_users_and_get_profile(engine: Engine, *, email_like: str):
    async with engine.acquire() as conn:
        result = await conn.execute(
            sa.select(
                users.c.first_name,
                users.c.last_name,
                users.c.email,
                invited_users.c.email.label("invitation_email"),
                invited_users.c.first_name.label("invitation_first_name"),
                invited_users.c.last_name.label("invitation_last_name"),
                invited_users.c.company_name,
                invited_users.c.phone.label("invitation_phone"),
                invited_users.c.address,
                invited_users.c.city,
                invited_users.c.state,
                invited_users.c.postal_code,
                invited_users.c.country,
                invited_users.c.accepted_by,
                users.c.status,
            )
            .select_from(
                invited_users.outerjoin(
                    users, users.c.id == invited_users.c.accepted_by
                )
            )
            .where(
                invited_users.c.email.like(email_like) | users.c.email.like(email_like)
            )
        )
        return await result.fetchall() or []


async def new_invited_user(
    engine: Engine, email: str, created_by: UserID, **other_values
):
    async with engine.acquire() as conn:
        await conn.execute(
            sa.insert(invited_users).values(
                created_by=created_by, email=email, **other_values
            )
        )
