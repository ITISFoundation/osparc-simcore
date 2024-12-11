import sqlalchemy as sa
from models_library.api_schemas_webserver.wallets import PaymentID
from models_library.groups import GroupID
from models_library.users import UserID
from simcore_postgres_database.models.payments_transactions import payments_transactions
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import users

from .base import BaseRepository


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
            return GroupID(row.primary_gid)

        msg = f"{user_id=} not found"
        raise ValueError(msg)

    async def get_notification_data(self, user_id: UserID, payment_id: PaymentID):
        """Retrives data that will be injected in a notification for the user on this payment"""
        if row := await self._get(
            sa.select(
                payments_transactions.c.payment_id,
                users.c.first_name,
                users.c.last_name,
                users.c.email,
                products.c.name.label("product_name"),
                products.c.display_name,
                products.c.vendor,
                products.c.support_email,
            )
            .select_from(
                sa.join(
                    sa.join(
                        payments_transactions,
                        users,
                        payments_transactions.c.user_id == users.c.id,
                    ),
                    products,
                    payments_transactions.c.product_name == products.c.name,
                )
            )
            .where(
                (payments_transactions.c.payment_id == payment_id)
                & (payments_transactions.c.user_id == user_id)
            )
        ):
            return row

        msg = f"{payment_id=} for {user_id=} was not found"
        raise ValueError(msg)
