from typing import TypeAlias

from models_library.api_schemas_webserver.wallets import PaymentMethodID
from models_library.basic_types import NonNegativeDecimal
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, PositiveInt
from simcore_postgres_database.utils_payments_autorecharge import AutoRechargeStmts

from ..core.errors import InvalidPaymentMethodError
from .base import BaseRepository

AutoRechargeID: TypeAlias = PositiveInt


class PaymentsAutorechargeDB(BaseModel):
    wallet_id: WalletID
    enabled: bool
    primary_payment_method_id: PaymentMethodID
    top_up_amount_in_usd: NonNegativeDecimal
    monthly_limit_in_usd: NonNegativeDecimal | None

    class Config:
        orm_mode = True


class AutoRechargeRepo(BaseRepository):
    async def get_wallet_autorecharge(
        self,
        wallet_id: WalletID,
    ) -> PaymentsAutorechargeDB | None:
        """Annotates init-payment transaction
        Raises:
            PaymentAlreadyExistsError
        """

        async with self.db_engine.begin() as conn:
            stmt = AutoRechargeStmts.get_wallet_autorecharge(wallet_id)
            result = await conn.execute(stmt)
            row = result.first()
            return PaymentsAutorechargeDB.from_orm(row) if row else None

    async def replace_wallet_autorecharge(
        self,
        user_id: UserID,
        wallet_id: WalletID,
        new: PaymentsAutorechargeDB,
    ) -> PaymentsAutorechargeDB:
        """
        Raises:
            InvalidPaymentMethodError: if `new` includes some invalid 'primary_payment_method_id'

        """
        async with self.db_engine.begin() as conn:
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
            row = result.first()
            assert row  # nosec
            return PaymentsAutorechargeDB.from_orm(row)
