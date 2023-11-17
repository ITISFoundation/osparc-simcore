import datetime

import simcore_postgres_database.errors as db_errors
import sqlalchemy as sa
from arrow import utcnow
from models_library.api_schemas_webserver.wallets import PaymentMethodID
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import parse_obj_as
from simcore_postgres_database.models.payments_methods import (
    InitPromptAckFlowState,
    payments_methods,
)

from ..core.errors import (
    PaymentMethodAlreadyAckedError,
    PaymentMethodNotFoundError,
    PaymentMethodUniqueViolationError,
)
from ..models.db import PaymentsMethodsDB
from .base import BaseRepository


class PaymentsMethodsRepo(BaseRepository):
    async def insert_init_payment_method(
        self,
        payment_method_id: PaymentMethodID,
        *,
        user_id: UserID,
        wallet_id: WalletID,
        initiated_at: datetime.datetime,
    ) -> PaymentMethodID:
        try:
            async with self.db_engine.begin() as conn:
                await conn.execute(
                    payments_methods.insert().values(
                        payment_method_id=payment_method_id,
                        user_id=user_id,
                        wallet_id=wallet_id,
                        initiated_at=initiated_at,
                    )
                )
                return payment_method_id

        except db_errors.UniqueViolation as err:
            raise PaymentMethodUniqueViolationError(
                payment_method_id=payment_method_id
            ) from err

    async def update_ack_payment_method(
        self,
        payment_method_id: PaymentMethodID,
        *,
        completion_state: InitPromptAckFlowState,
        state_message: str | None,
    ) -> PaymentsMethodsDB:
        if completion_state == InitPromptAckFlowState.PENDING:
            msg = f"{completion_state} is not a completion state"
            raise ValueError(msg)

        optional = {}
        if state_message:
            optional["state_message"] = state_message

        async with self.db_engine.begin() as conn:
            row = (
                await conn.execute(
                    sa.select(
                        payments_methods.c.initiated_at,
                        payments_methods.c.completed_at,
                    )
                    .where(payments_methods.c.payment_method_id == payment_method_id)
                    .with_for_update()
                )
            ).fetchone()

            if row is None:
                raise PaymentMethodNotFoundError(payment_method_id=payment_method_id)

            if row.completed_at is not None:
                raise PaymentMethodAlreadyAckedError(
                    payment_method_id=payment_method_id
                )

            result = await conn.execute(
                payments_methods.update()
                .values(completed_at=sa.func.now(), state=completion_state, **optional)
                .where(payments_methods.c.payment_method_id == payment_method_id)
                .returning(sa.literal_column("*"))
            )
            row = result.first()
            assert row, "execute above should have caught this"  # nosec

            return PaymentsMethodsDB.from_orm(row)

    async def insert_payment_method(
        self,
        payment_method_id: PaymentMethodID,
        *,
        user_id: UserID,
        wallet_id: WalletID,
        completion_state: InitPromptAckFlowState,
        state_message: str | None,
    ) -> PaymentsMethodsDB:
        await self.insert_init_payment_method(
            payment_method_id,
            user_id=user_id,
            wallet_id=wallet_id,
            initiated_at=utcnow().datetime,
        )
        return await self.update_ack_payment_method(
            payment_method_id,
            completion_state=completion_state,
            state_message=state_message,
        )

    async def list_user_payment_methods(
        self,
        *,
        user_id: UserID,
        wallet_id: WalletID,
    ) -> list[PaymentsMethodsDB]:
        # NOTE: we do not expect many payment methods, so no pagination is neede here
        async with self.db_engine.begin() as conn:
            result = await conn.execute(
                payments_methods.select()
                .where(
                    (payments_methods.c.user_id == user_id)
                    & (payments_methods.c.wallet_id == wallet_id)
                    & (payments_methods.c.state == InitPromptAckFlowState.SUCCESS)
                )
                .order_by(payments_methods.c.created.desc())
            )  # newest first
        rows = result.fetchall() or []
        return parse_obj_as(list[PaymentsMethodsDB], rows)

    async def get_payment_method_by_id(
        self,
        payment_method_id: PaymentMethodID,
    ) -> PaymentsMethodsDB:
        async with self.db_engine.begin() as conn:
            result = await conn.execute(
                payments_methods.select().where(
                    (payments_methods.c.payment_method_id == payment_method_id)
                    & (payments_methods.c.state == InitPromptAckFlowState.SUCCESS)
                )
            )
            row = result.first()
            if row is None:
                raise PaymentMethodNotFoundError(payment_method_id=payment_method_id)

            return PaymentsMethodsDB.from_orm(row)

    async def get_payment_method(
        self,
        payment_method_id: PaymentMethodID,
        *,
        user_id: UserID,
        wallet_id: WalletID,
    ) -> PaymentsMethodsDB:
        async with self.db_engine.begin() as conn:
            result = await conn.execute(
                payments_methods.select().where(
                    (payments_methods.c.user_id == user_id)
                    & (payments_methods.c.wallet_id == wallet_id)
                    & (payments_methods.c.payment_method_id == payment_method_id)
                    & (payments_methods.c.state == InitPromptAckFlowState.SUCCESS)
                )
            )
            row = result.first()
            if row is None:
                raise PaymentMethodNotFoundError(payment_method_id=payment_method_id)

            return PaymentsMethodsDB.from_orm(row)

    async def delete_payment_method(
        self,
        payment_method_id: PaymentMethodID,
        *,
        user_id: UserID,
        wallet_id: WalletID,
    ) -> PaymentsMethodsDB | None:
        async with self.db_engine.begin() as conn:
            result = await conn.execute(
                payments_methods.delete()
                .where(
                    (payments_methods.c.user_id == user_id)
                    & (payments_methods.c.wallet_id == wallet_id)
                    & (payments_methods.c.payment_method_id == payment_method_id)
                )
                .returning(sa.literal_column("*"))
            )
            row = result.first()
            return row if row is None else PaymentsMethodsDB.from_orm(row)
