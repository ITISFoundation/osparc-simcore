import datetime
import logging

import sqlalchemy as sa
import sqlalchemy.exc
from aiohttp import web
from models_library.api_schemas_webserver.wallets import PaymentMethodID
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, ConfigDict, TypeAdapter
from simcore_postgres_database.models.payments_methods import (
    InitPromptAckFlowState,
    payments_methods,
)
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.plugin import get_asyncpg_engine
from .errors import (
    PaymentMethodAlreadyAckedError,
    PaymentMethodNotFoundError,
    PaymentMethodUniqueViolationError,
)

_logger = logging.getLogger(__name__)


class PaymentsMethodsGetDB(BaseModel):
    payment_method_id: PaymentMethodID
    user_id: UserID
    wallet_id: WalletID
    # State in Flow
    initiated_at: datetime.datetime
    completed_at: datetime.datetime | None
    state: InitPromptAckFlowState
    state_message: str | None
    model_config = ConfigDict(from_attributes=True)


async def insert_init_payment_method(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    payment_method_id: str,
    user_id: UserID,
    wallet_id: WalletID,
    initiated_at: datetime.datetime,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        try:
            await conn.execute(
                payments_methods.insert().values(
                    payment_method_id=payment_method_id,
                    user_id=user_id,
                    wallet_id=wallet_id,
                    initiated_at=initiated_at,
                )
            )
        except sqlalchemy.exc.IntegrityError as err:
            raise PaymentMethodUniqueViolationError(payment_method_id=payment_method_id) from err


async def list_successful_payment_methods(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    wallet_id: WalletID,
) -> list[PaymentsMethodsGetDB]:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(
            sa.select(payments_methods)
            .where(
                (payments_methods.c.user_id == user_id)
                & (payments_methods.c.wallet_id == wallet_id)
                & (payments_methods.c.state == InitPromptAckFlowState.SUCCESS)
            )
            .order_by(payments_methods.c.created.desc())
        )  # newest first
        rows = result.fetchall()
        return TypeAdapter(list[PaymentsMethodsGetDB]).validate_python(rows)


async def get_successful_payment_method(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    payment_method_id: PaymentMethodID,
) -> PaymentsMethodsGetDB:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(
            sa.select(payments_methods).where(
                (payments_methods.c.user_id == user_id)
                & (payments_methods.c.wallet_id == wallet_id)
                & (payments_methods.c.payment_method_id == payment_method_id)
                & (payments_methods.c.state == InitPromptAckFlowState.SUCCESS)
            )
        )
        row = result.one_or_none()
        if row is None:
            raise PaymentMethodNotFoundError(payment_method_id=payment_method_id)

        return PaymentsMethodsGetDB.model_validate(row)


async def get_pending_payment_methods_ids(
    app: web.Application,
    connection: AsyncConnection | None = None,
) -> list[PaymentMethodID]:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(
            sa.select(payments_methods.c.payment_method_id)
            .where(payments_methods.c.completed_at.is_(None))
            .order_by(payments_methods.c.initiated_at.asc())  # oldest first
        )
        rows = result.fetchall()
        return [TypeAdapter(PaymentMethodID).validate_python(row.payment_method_id) for row in rows]


async def update_payment_method(
    app: web.Application,
    payment_method_id: PaymentMethodID,
    connection: AsyncConnection | None = None,
    *,
    state: InitPromptAckFlowState,
    state_message: str | None,
) -> PaymentsMethodsGetDB:
    """

    Raises:
        PaymentMethodNotFoundError
        PaymentMethodCompletedError
    """
    if state == InitPromptAckFlowState.PENDING:
        msg = f"{state} is not a completion state"
        raise ValueError(msg)

    optional = {}
    if state_message:
        optional["state_message"] = state_message

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(
            sa.select(
                payments_methods.c.initiated_at,
                payments_methods.c.completed_at,
            )
            .where(payments_methods.c.payment_method_id == payment_method_id)
            .with_for_update()
        )
        row = result.one_or_none()

        if row is None:
            raise PaymentMethodNotFoundError(payment_method_id=payment_method_id)

        if row.completed_at is not None:
            raise PaymentMethodAlreadyAckedError(payment_method_id=payment_method_id)

        result = await conn.execute(
            payments_methods.update()
            .values(completed_at=sa.func.now(), state=state, **optional)
            .where(payments_methods.c.payment_method_id == payment_method_id)
            .returning(payments_methods)
        )
        row = result.one()

        return PaymentsMethodsGetDB.model_validate(row)


async def delete_payment_method(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    payment_method_id: PaymentMethodID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            payments_methods.delete().where(
                (payments_methods.c.user_id == user_id)
                & (payments_methods.c.wallet_id == wallet_id)
                & (payments_methods.c.payment_method_id == payment_method_id)
            )
        )
