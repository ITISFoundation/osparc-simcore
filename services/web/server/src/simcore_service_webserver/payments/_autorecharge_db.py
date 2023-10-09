import logging
from typing import TypeAlias

from aiohttp import web
from models_library.api_schemas_webserver.wallets import PaymentMethodID
from models_library.basic_types import NonNegativeDecimal
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, PositiveInt
from simcore_postgres_database.utils_payments_autorecharge import AutoRechargeStmt

from ..db.plugin import get_database_engine

_logger = logging.getLogger(__name__)


AutoRechargeID: TypeAlias = PositiveInt


class PaymentsAutorechargeDB(BaseModel):
    wallet_id: WalletID
    enabled: bool
    primary_payment_method_id: PaymentMethodID
    min_balance_in_usd: NonNegativeDecimal
    top_up_amount_in_usd: NonNegativeDecimal
    top_up_countdown: PositiveInt | None

    class Config:
        orm_mode = True


async def get_wallet_autorecharge(
    app: web.Application,
    *,
    wallet_id: WalletID,
) -> PaymentsAutorechargeDB | None:
    async with get_database_engine(app).acquire() as conn:
        # has recharge trigger?
        stmt = AutoRechargeStmt.get_wallet_autorecharge(wallet_id)
        result = await conn.execute(stmt)
        row = await result.first()
        return PaymentsAutorechargeDB.from_orm(row) if row else None


async def replace_wallet_autorecharge(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    auto_recharge: PaymentsAutorechargeDB,
) -> PaymentsAutorechargeDB:
    async with get_database_engine(app).acquire() as conn:
        stmt = AutoRechargeStmt.is_valid_payment_method(
            user_id=user_id,
            wallet_id=auto_recharge.wallet_id,
            payment_method_id=auto_recharge.primary_payment_method_id,
        )

        if await conn.scalar(stmt) != auto_recharge.primary_payment_method_id:
            raise ValueError("invalid payment method")

        # if it does nto exist create, otherwise update
        # TODO:
        stmt = AutoRechargeStmt.update_wallet_autorecharge(
            wallet_id,
        )
        result = await conn.execute(stmt)
        row = await result.first()
        return PaymentsAutorechargeDB.from_orm(row) if row else None
