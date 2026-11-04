import logging

import sqlalchemy as sa
from models_library.api_schemas_webserver.wallets import PaymentID
from models_library.groups import GroupID, GroupIDAdapter
from models_library.products import ProductName
from models_library.shared_user_preferences import InvoiceEmailRecipientsFrontendUserPreference
from models_library.users import UserID
from pydantic import EmailStr, ValidationError
from simcore_postgres_database.models.payments_transactions import payments_transactions
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils_user_preferences import FrontendUserPreferencesRepo

from .base import BaseRepository

_logger = logging.getLogger(__name__)


class PaymentsUsersRepo(BaseRepository):
    # NOTE:
    # Currently linked to `users` but expected to be linked to `payments_users`
    # when databases are separated. The latter will be a subset copy of the former.
    #

    async def _get(self, query):
        async with self.db_engine.begin() as conn:
            result = await conn.execute(query)
            return result.first()

    async def get_primary_group_id(self, user_id: UserID) -> GroupID:
        if row := await self._get(
            sa.select(
                users.c.primary_gid,
            ).where(users.c.id == user_id)
        ):
            return GroupIDAdapter.validate_python(row.primary_gid)

        msg = f"{user_id=} not found"
        raise ValueError(msg)

    async def get_notification_data(self, user_id: UserID, payment_id: PaymentID):
        """Retrieves data that will be injected in a notification for the user on this payment"""
        if row := await self._get(
            sa.select(
                payments_transactions.c.payment_id,
                payments_transactions.c.product_name,
                users.c.name.label("user_name"),
                users.c.first_name,
                users.c.last_name,
                users.c.email,
                users.c.language,
            )
            .select_from(
                sa.join(
                    payments_transactions,
                    users,
                    payments_transactions.c.user_id == users.c.id,
                )
            )
            .where((payments_transactions.c.payment_id == payment_id) & (payments_transactions.c.user_id == user_id))
        ):
            return row

        msg = f"{payment_id=} for {user_id=} was not found"
        raise ValueError(msg)

    async def get_invoice_email_recipients(self, user_id: UserID, product_name: ProductName) -> list[EmailStr]:
        preference_name = f"{user_id}/{InvoiceEmailRecipientsFrontendUserPreference.get_preference_name()}"
        async with self.db_engine.begin() as conn:
            payload = await FrontendUserPreferencesRepo.load(
                conn,
                user_id=user_id,
                product_name=product_name,
                preference_name=preference_name,
            )

        if payload is None:
            return []

        try:
            preference = InvoiceEmailRecipientsFrontendUserPreference.model_validate(payload)
        except ValidationError:
            _logger.warning(
                "Ignoring invalid invoice email recipient preference for %s and %s",
                user_id,
                product_name,
            )
            return []
        return preference.value
