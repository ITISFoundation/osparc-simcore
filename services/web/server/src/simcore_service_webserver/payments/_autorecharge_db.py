import logging
from typing import TypeAlias

from aiohttp import web
from models_library.api_schemas_webserver.wallets import PaymentMethodID
from models_library.basic_types import NonNegativeDecimal
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, ConfigDict, PositiveInt
from simcore_postgres_database.utils_payments_autorecharge import AutoRechargeStatements
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.plugin import get_asyncpg_engine
from .errors import InvalidPaymentMethodError

_logger = logging.getLogger(__name__)


AutoRechargeID: TypeAlias = PositiveInt


class PaymentsAutorechargeGetDB(BaseModel):
    wallet_id: WalletID
    enabled: bool
    primary_payment_method_id: PaymentMethodID
    top_up_amount_in_usd: NonNegativeDecimal
    monthly_limit_in_usd: NonNegativeDecimal | None
    model_config = ConfigDict(from_attributes=True)


async def get_wallet_autorecharge(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    wallet_id: WalletID,
) -> PaymentsAutorechargeGetDB | None:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        stmt = AutoRechargeStatements.get_wallet_autorecharge(wallet_id)
        result = await conn.execute(stmt)
        row = result.one_or_none()
        return PaymentsAutorechargeGetDB.model_validate(row) if row else None


async def replace_wallet_autorecharge(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    new: PaymentsAutorechargeGetDB,
) -> PaymentsAutorechargeGetDB:
    """
    Raises:
        InvalidPaymentMethodError: if `new` includes some invalid 'primary_payment_method_id'

    """
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        stmt = AutoRechargeStatements.is_valid_payment_method(
            user_id=user_id,
            wallet_id=new.wallet_id,
            payment_method_id=new.primary_payment_method_id,
        )

        if await conn.scalar(stmt) != new.primary_payment_method_id:
            raise InvalidPaymentMethodError(payment_method_id=new.primary_payment_method_id)

        stmt = AutoRechargeStatements.upsert_wallet_autorecharge(
            wallet_id=wallet_id,
            enabled=new.enabled,
            primary_payment_method_id=new.primary_payment_method_id,
            top_up_amount_in_usd=new.top_up_amount_in_usd,
            monthly_limit_in_usd=new.monthly_limit_in_usd,
        )
        result = await conn.execute(stmt)
        row = result.one()
        return PaymentsAutorechargeGetDB.model_validate(row)
