""" Database API

    - Adds a layer to the postgres API with a focus on the projects comments

"""
import logging
from datetime import datetime

from aiohttp import web
from models_library.users import GroupID
from models_library.wallets import WalletID
from pydantic import BaseModel, TypeAdapter
from simcore_postgres_database.models.wallet_to_groups import wallet_to_groups
from sqlalchemy import func, literal_column
from sqlalchemy.sql import select

from ..db.plugin import get_database_engine
from .errors import WalletGroupNotFoundError

_logger = logging.getLogger(__name__)

### Models


class WalletGroupGetDB(BaseModel):
    gid: GroupID
    read: bool
    write: bool
    delete: bool
    created: datetime
    modified: datetime


## DB API


async def create_wallet_group(
    app: web.Application,
    wallet_id: WalletID,
    group_id: GroupID,
    *,
    read: bool,
    write: bool,
    delete: bool,
) -> WalletGroupGetDB:
    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(
            wallet_to_groups.insert()
            .values(
                wallet_id=wallet_id,
                gid=group_id,
                read=read,
                write=write,
                delete=delete,
                created=func.now(),
                modified=func.now(),
            )
            .returning(literal_column("*"))
        )
        row = await result.first()
        return WalletGroupGetDB.model_validate(row)


async def list_wallet_groups(
    app: web.Application,
    wallet_id: WalletID,
) -> list[WalletGroupGetDB]:
    stmt = (
        select(
            wallet_to_groups.c.gid,
            wallet_to_groups.c.read,
            wallet_to_groups.c.write,
            wallet_to_groups.c.delete,
            wallet_to_groups.c.created,
            wallet_to_groups.c.modified,
        )
        .select_from(wallet_to_groups)
        .where(wallet_to_groups.c.wallet_id == wallet_id)
    )

    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(stmt)
        rows = await result.fetchall() or []
        return TypeAdapter(list[WalletGroupGetDB]).validate_python(rows)


async def get_wallet_group(
    app: web.Application,
    wallet_id: WalletID,
    group_id: GroupID,
) -> WalletGroupGetDB:
    stmt = (
        select(
            wallet_to_groups.c.gid,
            wallet_to_groups.c.read,
            wallet_to_groups.c.write,
            wallet_to_groups.c.delete,
            wallet_to_groups.c.created,
            wallet_to_groups.c.modified,
        )
        .select_from(wallet_to_groups)
        .where(
            (wallet_to_groups.c.wallet_id == wallet_id)
            & (wallet_to_groups.c.gid == group_id)
        )
    )

    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(stmt)
        row = await result.first()
        if row is None:
            raise WalletGroupNotFoundError(
                reason=f"Wallet {wallet_id} group {group_id} not found"
            )
        return WalletGroupGetDB.model_validate(row)


async def update_wallet_group(
    app: web.Application,
    wallet_id: WalletID,
    group_id: GroupID,
    *,
    read: bool,
    write: bool,
    delete: bool,
) -> WalletGroupGetDB:
    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(
            wallet_to_groups.update()
            .values(
                read=read,
                write=write,
                delete=delete,
            )
            .where(
                (wallet_to_groups.c.wallet_id == wallet_id)
                & (wallet_to_groups.c.gid == group_id)
            )
            .returning(literal_column("*"))
        )
        row = await result.first()
        if row is None:
            raise WalletGroupNotFoundError(
                reason=f"Wallet {wallet_id} group {group_id} not found"
            )
        return WalletGroupGetDB.model_validate(row)


async def delete_wallet_group(
    app: web.Application,
    wallet_id: WalletID,
    group_id: GroupID,
) -> None:
    async with get_database_engine(app).acquire() as conn:
        await conn.execute(
            wallet_to_groups.delete().where(
                (wallet_to_groups.c.wallet_id == wallet_id)
                & (wallet_to_groups.c.gid == group_id)
            )
        )
