import sqlalchemy as sa
from models_library.api_schemas_webserver.wallets import PaymentID
from models_library.products import ProductName
from models_library.users import UserID
from simcore_postgres_database.models.jinja2_templates import jinja2_templates
from simcore_postgres_database.models.payments_transactions import payments_transactions
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import users

from ._db import BaseDataRepo


class PaymentsDataRepo(BaseDataRepo):
    async def get_on_payed_data(self, user_id: UserID, payment_id: PaymentID):
        """Retrieves payment data for the templates on the `on_payed` event"""
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

    async def get_email_templates(self, names: set[str], product: ProductName):
        # TODO: create products_to_template table and add a join here
        async with self.db_engine.begin() as conn:
            result = await conn.execute(
                sa.select(
                    jinja2_templates.c.name,
                    jinja2_templates.c.content,
                ).where(jinja2_templates.c.name.in_(names))
            )
            return result.fetchall()
