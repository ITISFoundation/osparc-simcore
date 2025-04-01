import sqlalchemy as sa
from models_library.api_schemas_webserver.wallets import PaymentID
from models_library.users import UserID
from simcore_postgres_database.models.payments_transactions import payments_transactions
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils_repos import pass_or_acquire_connection

from ._repository import _BaseRepo


class PaymentsDataRepo(_BaseRepo):
    # NOSONAR
    # NOTE: this is for the moment duplicated from the payments until completed
    # then it will be replaced
    async def get_on_payed_data(self, user_id: UserID, payment_id: PaymentID):
        """Retrieves payment data for the templates on the `on_payed` event"""
        query = (
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
        )

        async with pass_or_acquire_connection(self.db_engine) as conn:
            result = await conn.execute(query)
            row = result.one_or_none()

        if not row:
            msg = f"{payment_id=} for {user_id=} was not found"
            raise ValueError(msg)

        return row
