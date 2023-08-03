""" Database API

    - Adds a layer to the postgres API with a focus on the projects comments

"""
import logging

from aiohttp import web
from models_library.users import GroupID, UserID
from models_library.wallets import UserWalletDB, WalletDB, WalletID, WalletStatus
from pydantic import parse_obj_as
from simcore_postgres_database.models.groups import user_to_groups
from simcore_postgres_database.models.wallet_to_groups import wallet_to_groups
from simcore_postgres_database.models.wallets import wallets
from sqlalchemy import func, literal_column
from sqlalchemy.dialects.postgresql import BOOLEAN, INTEGER
from sqlalchemy.sql import select

from ..db.plugin import get_database_engine
from .errors import WalletAccessForbiddenError, WalletNotFoundError

_logger = logging.getLogger(__name__)


async def create_wallet(
    app: web.Application,
    owner: GroupID,
    wallet_name: str,
    description: str | None,
    thumbnail: str | None,
) -> WalletDB:
    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(
            wallets.insert()
            .values(
                name=wallet_name,
                description=description,
                owner=owner,
                thumbnail=thumbnail,
                status=WalletStatus.ACTIVE,
                created=func.now(),
                modified=func.now(),
            )
            .returning(literal_column("*"))
        )
        row = await result.first()
        return parse_obj_as(WalletDB, row)


async def list_wallets_for_user(
    app: web.Application,
    user_id: UserID,
) -> list[UserWalletDB]:
    stmt = (
        select(
            wallets.c.wallet_id,
            wallets.c.name,
            wallets.c.description,
            wallets.c.owner,
            wallets.c.thumbnail,
            wallets.c.status,
            wallets.c.created,
            wallets.c.modified,
            func.max(wallet_to_groups.c.read.cast(INTEGER)).cast(BOOLEAN).label("read"),
            func.max(wallet_to_groups.c.write.cast(INTEGER))
            .cast(BOOLEAN)
            .label("write"),
            func.max(wallet_to_groups.c.delete.cast(INTEGER))
            .cast(BOOLEAN)
            .label("delete"),
        )
        .select_from(
            user_to_groups.join(
                wallet_to_groups, user_to_groups.c.gid == wallet_to_groups.c.gid
            ).join(wallets, wallet_to_groups.c.wallet_id == wallets.c.wallet_id)
        )
        .where(
            (user_to_groups.c.uid == user_id)
            & (user_to_groups.c.access_rights["read"].astext == "true")
        )
        .group_by(
            wallets.c.wallet_id,
            wallets.c.name,
            wallets.c.description,
            wallets.c.owner,
            wallets.c.thumbnail,
            wallets.c.status,
            wallets.c.created,
            wallets.c.modified,
        )
    )

    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(stmt)
        output: list[UserWalletDB] = []
        for row in await result.fetchall():
            output.append(parse_obj_as(UserWalletDB, row))
        return output


async def get_wallet_for_user(
    app: web.Application,
    user_id: UserID,
    wallet_id: WalletID,
) -> UserWalletDB:
    stmt = (
        select(
            wallets.c.wallet_id,
            wallets.c.name,
            wallets.c.description,
            wallets.c.owner,
            wallets.c.thumbnail,
            wallets.c.status,
            wallets.c.created,
            wallets.c.modified,
            func.max(wallet_to_groups.c.read.cast(INTEGER)).cast(BOOLEAN).label("read"),
            func.max(wallet_to_groups.c.write.cast(INTEGER))
            .cast(BOOLEAN)
            .label("write"),
            func.max(wallet_to_groups.c.delete.cast(INTEGER))
            .cast(BOOLEAN)
            .label("delete"),
        )
        .select_from(
            user_to_groups.join(
                wallet_to_groups, user_to_groups.c.gid == wallet_to_groups.c.gid
            ).join(wallets, wallet_to_groups.c.wallet_id == wallets.c.wallet_id)
        )
        .where(
            (user_to_groups.c.uid == user_id)
            & (user_to_groups.c.access_rights["read"].astext == "true")
            & (wallets.c.wallet_id == wallet_id)
        )
        .group_by(
            wallets.c.wallet_id,
            wallets.c.name,
            wallets.c.description,
            wallets.c.owner,
            wallets.c.thumbnail,
            wallets.c.status,
            wallets.c.created,
            wallets.c.modified,
        )
    )

    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(stmt)
        row = await result.first()
        if row is None:
            raise WalletAccessForbiddenError(
                reason=f"User does not have access to the wallet {wallet_id}. Or wallet does not exist.",
            )
        return parse_obj_as(UserWalletDB, row)


async def get_wallet(app: web.Application, wallet_id: WalletID) -> WalletDB:
    stmt = (
        select(
            wallets.c.wallet_id,
            wallets.c.name,
            wallets.c.description,
            wallets.c.owner,
            wallets.c.thumbnail,
            wallets.c.status,
            wallets.c.created,
            wallets.c.modified,
        )
        .select_from(wallets)
        .where(wallets.c.wallet_id == wallet_id)
    )
    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(stmt)
        row = await result.first()
        if row is None:
            raise WalletNotFoundError(reason=f"Wallet {wallet_id} not found.")
        return parse_obj_as(WalletDB, row)


async def update_wallet(
    app: web.Application,
    wallet_id: WalletID,
    name: str,
    description: str,
    thumbnail: str,
    status: WalletStatus,
) -> WalletDB:
    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(
            wallets.update()
            .values(
                name=name,
                description=description,
                thumbnail=thumbnail,
                status=status,
                modified=func.now(),
            )
            .where(wallets.c.wallet_id == wallet_id)
            .returning(literal_column("*"))
        )
        row = await result.first()
        if row is None:
            raise WalletNotFoundError(reason=f"Wallet {wallet_id} not found.")
        return parse_obj_as(WalletDB, row)


async def delete_wallet(
    app: web.Application,
    wallet_id: WalletID,
) -> None:
    async with get_database_engine(app).acquire() as conn:
        await conn.execute(wallets.delete().where(wallets.c.wallet_id == wallet_id))
