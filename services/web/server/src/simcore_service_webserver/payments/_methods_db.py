import datetime
import logging

import simcore_postgres_database.errors as db_errors
import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.result import ResultProxy
from models_library.api_schemas_webserver.wallets import PaymentMethodID
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, PositiveInt, parse_obj_as
from simcore_postgres_database.models.payments_methods import (
    InitPromptAckFlowState,
    payments_methods,
)
from sqlalchemy import literal_column
from sqlalchemy.sql import func

from ..db.plugin import get_database_engine
from .errors import (
    PaymentMethodAlreadyAckedError,
    PaymentMethodNotFoundError,
    PaymentMethodUniqueViolationError,
)

_logger = logging.getLogger(__name__)


#
class PaymentsMethodsDB(BaseModel):
    payment_method_id: PaymentMethodID
    user_id: UserID
    wallet_id: WalletID
    # State in Flow
    initiated_at: datetime.datetime
    completed_at: datetime.datetime | None
    state: InitPromptAckFlowState
    state_message: str | None

    class Config:
        orm_mode = True


async def insert_init_payment_method(
    app: web.Application,
    *,
    payment_method_id: str,
    user_id: UserID,
    wallet_id: WalletID,
    initiated_at: datetime.datetime,
) -> None:
    async with get_database_engine(app).acquire() as conn:
        try:
            await conn.execute(
                payments_methods.insert().values(
                    payment_method_id=payment_method_id,
                    user_id=user_id,
                    wallet_id=wallet_id,
                    initiated_at=initiated_at,
                )
            )
        except db_errors.UniqueViolation as err:
            raise PaymentMethodUniqueViolationError(
                payment_method_id=payment_method_id
            ) from err


async def list_payments_methods(
    app,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    offset: PositiveInt | None = None,
    limit: PositiveInt | None = None,
) -> tuple[int, list[PaymentsMethodsDB]]:
    """List payments entries done by a give user (in any state)

    Sorted by newest-first
    """

    async with get_database_engine(app).acquire() as conn:
        total_number_of_items = await conn.scalar(
            sa.select(sa.func.count())
            .select_from(payments_methods)
            .where(
                (payments_methods.c.user_id == user_id)
                & (payments_methods.c.wallet_id == wallet_id)
            )
        )
        assert total_number_of_items is not None  # nosec

        query = (
            payments_methods.select()
            .where(
                (payments_methods.c.user_id == user_id)
                & (payments_methods.c.wallet_id == wallet_id)
            )
            .order_by(payments_methods.c.created.desc())
        )  # newest first

        # NOTE: what if between these two calls there are new rows? can we get this in an atomic call?
        if offset is not None:
            if offset > total_number_of_items:
                msg = f"{offset=} exceeds {total_number_of_items=}"
                raise ValueError(msg)

            query.offset(offset)

            if limit is not None:
                query.limit(limit)

        result: ResultProxy = await conn.execute(query)
        rows = await result.fetchall() or []
        page = parse_obj_as(list[PaymentsMethodsDB], rows)
        return total_number_of_items, page


async def list_successful_payment_methods(
    app,
    *,
    user_id: UserID,
    wallet_id: WalletID,
) -> list[PaymentsMethodsDB]:
    async with get_database_engine(app).acquire() as conn:
        result: ResultProxy = await conn.execute(
            payments_methods.select()
            .where(
                (payments_methods.c.user_id == user_id)
                & (payments_methods.c.wallet_id == wallet_id)
                & (payments_methods.c.state == InitPromptAckFlowState.SUCCESS)
            )
            .order_by(payments_methods.c.created.desc())
        )  # newest first
        rows = await result.fetchall() or []
        return parse_obj_as(list[PaymentsMethodsDB], rows)


async def get_successful_payment_method(
    app,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    payment_method_id: PaymentMethodID,
) -> PaymentsMethodsDB:
    async with get_database_engine(app).acquire() as conn:
        result: ResultProxy = await conn.execute(
            payments_methods.select().where(
                (payments_methods.c.user_id == user_id)
                & (payments_methods.c.wallet_id == wallet_id)
                & (payments_methods.c.payment_method_id == payment_method_id)
                & (payments_methods.c.state == InitPromptAckFlowState.SUCCESS)
            )
        )
        row = await result.first()
        if row is None:
            raise PaymentMethodNotFoundError(payment_method_id=payment_method_id)

        return PaymentsMethodsDB.from_orm(row)


async def get_pending_payment_methods_ids(
    app: web.Application,
) -> list[PaymentMethodID]:
    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(
            sa.select(payments_methods.c.payment_method_id)
            .where(payments_methods.c.completed_at == None)  # noqa: E711
            .order_by(payments_methods.c.initiated_at.asc())  # oldest first
        )
        rows = await result.fetchall() or []
        return [parse_obj_as(PaymentMethodID, row.payment_method_id) for row in rows]


async def udpate_payment_method(
    app: web.Application,
    payment_method_id: PaymentMethodID,
    *,
    state: InitPromptAckFlowState,
    state_message: str | None,
) -> PaymentsMethodsDB:
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

    async with get_database_engine(app).acquire() as conn, conn.begin():
        row = await (
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
            raise PaymentMethodAlreadyAckedError(payment_method_id=payment_method_id)

        result = await conn.execute(
            payments_methods.update()
            .values(completed_at=func.now(), state=state, **optional)
            .where(payments_methods.c.payment_method_id == payment_method_id)
            .returning(literal_column("*"))
        )
        row = await result.first()
        assert row, "execute above should have caught this"  # nosec

        return PaymentsMethodsDB.from_orm(row)


async def delete_payment_method(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    payment_method_id: PaymentMethodID,
):
    async with get_database_engine(app).acquire() as conn:
        await conn.execute(
            payments_methods.delete().where(
                (payments_methods.c.user_id == user_id)
                & (payments_methods.c.wallet_id == wallet_id)
                & (payments_methods.c.payment_method_id == payment_method_id)
            )
        )
