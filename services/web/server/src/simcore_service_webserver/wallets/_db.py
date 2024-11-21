""" Database API

    - Adds a layer to the postgres API with a focus on the projects comments

"""
import logging

from aiohttp import web
from models_library.products import ProductName
from models_library.users import GroupID, UserID
from models_library.wallets import UserWalletDB, WalletDB, WalletID, WalletStatus
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
    product_name: ProductName,
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
                product_name=product_name,
            )
            .returning(literal_column("*"))
        )
        row = await result.first()
        return WalletDB.model_validate(row)


_SELECTION_ARGS = (
    wallets.c.wallet_id,
    wallets.c.name,
    wallets.c.description,
    wallets.c.owner,
    wallets.c.thumbnail,
    wallets.c.status,
    wallets.c.created,
    wallets.c.modified,
    func.max(wallet_to_groups.c.read.cast(INTEGER)).cast(BOOLEAN).label("read"),
    func.max(wallet_to_groups.c.write.cast(INTEGER)).cast(BOOLEAN).label("write"),
    func.max(wallet_to_groups.c.delete.cast(INTEGER)).cast(BOOLEAN).label("delete"),
)

_JOIN_TABLES = user_to_groups.join(
    wallet_to_groups, user_to_groups.c.gid == wallet_to_groups.c.gid
).join(wallets, wallet_to_groups.c.wallet_id == wallets.c.wallet_id)


async def list_wallets_for_user(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
) -> list[UserWalletDB]:
    stmt = (
        select(*_SELECTION_ARGS)
        .select_from(_JOIN_TABLES)
        .where(
            (user_to_groups.c.uid == user_id)
            & (user_to_groups.c.access_rights["read"].astext == "true")
            & (wallets.c.product_name == product_name)
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
        rows = await result.fetchall() or []
        output: list[UserWalletDB] = [UserWalletDB.model_validate(row) for row in rows]
        return output


async def list_wallets_owned_by_user(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
) -> list[WalletID]:
    stmt = (
        select(wallets.c.wallet_id)
        .select_from(_JOIN_TABLES)
        .where(
            (user_to_groups.c.uid == user_id)
            & (user_to_groups.c.gid == wallets.c.owner)
            & (wallets.c.product_name == product_name)
        )
    )
    async with get_database_engine(app).acquire() as conn:
        results = await conn.execute(stmt)
        rows = await results.fetchall() or []
        return [row.wallet_id for row in rows]


async def get_wallet_for_user(
    app: web.Application,
    user_id: UserID,
    wallet_id: WalletID,
    product_name: ProductName,
) -> UserWalletDB:
    stmt = (
        select(*_SELECTION_ARGS)
        .select_from(_JOIN_TABLES)
        .where(
            (user_to_groups.c.uid == user_id)
            & (user_to_groups.c.access_rights["read"].astext == "true")
            & (wallets.c.wallet_id == wallet_id)
            & (wallets.c.product_name == product_name)
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
                user_id=user_id,
                wallet_id=wallet_id,
                product_name=product_name,
            )
        return UserWalletDB.model_validate(row)


async def get_wallet(
    app: web.Application, wallet_id: WalletID, product_name: ProductName
) -> WalletDB:
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
        .where(
            (wallets.c.wallet_id == wallet_id)
            & (wallets.c.product_name == product_name)
        )
    )
    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(stmt)
        row = await result.first()
        if row is None:
            raise WalletNotFoundError(reason=f"Wallet {wallet_id} not found.")
        return WalletDB.model_validate(row)


async def update_wallet(
    app: web.Application,
    wallet_id: WalletID,
    name: str,
    description: str | None,
    thumbnail: str | None,
    status: WalletStatus,
    product_name: ProductName,
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
            .where(
                (wallets.c.wallet_id == wallet_id)
                & (wallets.c.product_name == product_name)
            )
            .returning(literal_column("*"))
        )
        row = await result.first()
        if row is None:
            raise WalletNotFoundError(reason=f"Wallet {wallet_id} not found.")
        return WalletDB.model_validate(row)


async def delete_wallet(
    app: web.Application,
    wallet_id: WalletID,
    product_name: ProductName,
) -> None:
    async with get_database_engine(app).acquire() as conn:
        await conn.execute(
            wallets.delete().where(
                (wallets.c.wallet_id == wallet_id)
                & (wallets.c.product_name == product_name)
            )
        )
