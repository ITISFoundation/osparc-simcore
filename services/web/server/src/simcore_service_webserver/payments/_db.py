import datetime
import logging
from decimal import Decimal

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.result import ResultProxy
from models_library.api_schemas_webserver.wallets import PaymentID
from models_library.basic_types import IDStr
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, PositiveInt, parse_obj_as
from simcore_postgres_database.models.payments_transactions import payments_transactions
from sqlalchemy import literal_column
from sqlalchemy.sql import func

from ..db.plugin import get_database_engine

_logger = logging.getLogger(__name__)


#
# NOTE: this will be moved to the payments service
# NOTE: with https://sqlmodel.tiangolo.com/ we would only define this once!
class PaymentsTransactionsDB(BaseModel):
    payment_id: IDStr
    price_dollars: Decimal  # accepts negatives
    osparc_credits: Decimal  # accepts negatives
    product_name: ProductName
    user_id: UserID
    user_email: LowerCaseEmailStr
    wallet_id: WalletID
    comment: str | None
    initiated_at: datetime.datetime
    completed_at: datetime.datetime | None
    success: bool | None
    errors: str | None


async def create_payment_transaction(  # noqa: PLR0913
    app: web.Application,
    *,
    payment_id: str,
    price_dollars: Decimal,
    osparc_credits: Decimal,
    product_name: str,
    user_id: UserID,
    user_email: str,
    wallet_id: WalletID,
    comment: str | None,
    initiated_at: datetime.datetime,
) -> PaymentsTransactionsDB:
    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(
            payments_transactions.insert()
            .values(
                payment_id=payment_id,
                price_dollars=price_dollars,
                osparc_credits=osparc_credits,
                product_name=product_name,
                user_id=user_id,
                user_email=user_email,
                wallet_id=wallet_id,
                comment=comment,
                initiated_at=initiated_at,
            )
            .returning(literal_column("*"))
        )
        row = await result.first()
        assert row  #  nosec
        return PaymentsTransactionsDB.parse_obj(dict(row.items()))


async def list_user_payment_transactions(
    app,
    *,
    user_id: UserID,
    offset: PositiveInt,
    limit: PositiveInt,
) -> tuple[int, list[PaymentsTransactionsDB]]:
    """List payments done by a give user

    Sorted by newest-first
    """
    async with get_database_engine(app).acquire() as conn:
        total_number_of_items = await conn.scalar(
            sa.select(sa.func.count())
            .select_from(payments_transactions)
            .where(payments_transactions.c.user_id == user_id)
        )
        assert total_number_of_items is not None  # nosec

        # NOTE: what if between these two calls there are new rows? can we get this in an atomic call?
        if offset > total_number_of_items:
            msg = f"{offset=} exceeds {total_number_of_items=}"
            raise ValueError(msg)

        result: ResultProxy = await conn.execute(
            payments_transactions.select()
            .where(payments_transactions.c.user_id == user_id)
            .order_by(payments_transactions.c.created.desc())  # newest first
            .offset(offset)
            .limit(limit)
        )
        rows = await result.fetchall() or []
        page = parse_obj_as(list[PaymentsTransactionsDB], rows)
        return total_number_of_items, page


async def get_pending_payment_transactions_ids(app: web.Application) -> list[PaymentID]:
    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(
            sa.select(payments_transactions.c.payment_id)
            .where(payments_transactions.c.completed_at == None)  # noqa: E711
            .order_by(payments_transactions.c.initiated_at.asc())  # oldest first
        )
        rows = await result.fetchall() or []
        return [parse_obj_as(PaymentID, idr) for idr in rows]


async def complete_payment_transaction(
    app: web.Application, *, payment_id: PaymentID, success: bool, error_msg: str | None
) -> PaymentsTransactionsDB:
    optional = {}
    if error_msg:
        optional["errors"] = error_msg

    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(
            payments_transactions.update()
            .values(completed_at=func.now(), success=success, **optional)
            .where(payments_transactions.c.payment_id == payment_id)
            .returning(literal_column("*"))
        )
        row = await result.first()
        assert row  #  nosec
        return PaymentsTransactionsDB.parse_obj(dict(row.items()))
