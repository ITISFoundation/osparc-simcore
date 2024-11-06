import logging
from typing import TypeAlias

from aiohttp import web
from models_library.api_schemas_webserver.wallets import PaymentMethodID
from models_library.basic_types import NonNegativeDecimal
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, ConfigDict, PositiveInt
from simcore_postgres_database.utils_payments_autorecharge import AutoRechargeStmts

from ..db.plugin import get_database_engine
from .errors import InvalidPaymentMethodError

_logger = logging.getLogger(__name__)


AutoRechargeID: TypeAlias = PositiveInt


class PaymentsAutorechargeDB(BaseModel):
    wallet_id: WalletID
    enabled: bool
    primary_payment_method_id: PaymentMethodID
    top_up_amount_in_usd: NonNegativeDecimal
    monthly_limit_in_usd: NonNegativeDecimal | None
    model_config = ConfigDict(from_attributes=True)


async def get_wallet_autorecharge(
    app: web.Application,
    *,
    wallet_id: WalletID,
) -> PaymentsAutorechargeDB | None:
    async with get_database_engine(app).acquire() as conn:
        stmt = AutoRechargeStmts.get_wallet_autorecharge(wallet_id)
        result = await conn.execute(stmt)
        row = await result.first()
        return PaymentsAutorechargeDB.model_validate(row) if row else None


async def replace_wallet_autorecharge(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    new: PaymentsAutorechargeDB,
) -> PaymentsAutorechargeDB:
    """
    Raises:
        InvalidPaymentMethodError: if `new` includes some invalid 'primary_payment_method_id'

    """
    async with get_database_engine(app).acquire() as conn:
        stmt = AutoRechargeStmts.is_valid_payment_method(
            user_id=user_id,
            wallet_id=new.wallet_id,
            payment_method_id=new.primary_payment_method_id,
        )

        if await conn.scalar(stmt) != new.primary_payment_method_id:
            raise InvalidPaymentMethodError(
                payment_method_id=new.primary_payment_method_id
            )

        stmt = AutoRechargeStmts.upsert_wallet_autorecharge(
            wallet_id=wallet_id,
            enabled=new.enabled,
            primary_payment_method_id=new.primary_payment_method_id,
            top_up_amount_in_usd=new.top_up_amount_in_usd,
            monthly_limit_in_usd=new.monthly_limit_in_usd,
        )
        result = await conn.execute(stmt)
        row = await result.first()
        assert row  # nosec
        return PaymentsAutorechargeDB.model_validate(row)
