import sqlalchemy as sa
from models_library.products import ProductName
from models_library.users import UserID
from simcore_postgres_database.models.jinja2_templates import jinja2_templates
from simcore_postgres_database.models.products_to_templates import products_to_templates
from simcore_postgres_database.models.users import users
from sqlalchemy.ext.asyncio import AsyncEngine


class _BaseRepo:
    def __init__(self, db_engine: AsyncEngine):
        assert db_engine is not None  # nosec
        self.db_engine = db_engine

    async def _get(self, query):
        async with self.db_engine.begin() as conn:
            result = await conn.execute(query)
            return result.first()


class UsersRepo(_BaseRepo):
    async def get_user_data(self, user_id: UserID):
        return await self._get(
            sa.select(
                users.c.first_name,
                users.c.last_name,
                users.c.email,
            ).where(users.c.id == user_id)
        )


class TemplatesRepo(_BaseRepo):
    async def iter_email_templates(self, product_name: ProductName):
        async with self.db_engine.begin() as conn:
            async for row in await conn.stream(
                sa.select(
                    jinja2_templates.c.name,
                    jinja2_templates.c.content,
                )
                .select_from(products_to_templates.join(jinja2_templates))
                .where(
                    (products_to_templates.c.product_name == product_name)
                    & (jinja2_templates.c.name.ilike("%.email.%"))
                )
            ):
                yield row

    async def iter_product_templates(self, product_name: ProductName):
        async with self.db_engine.begin() as conn:
            async for row in await conn.stream(
                sa.select(
                    products_to_templates.c.product_name,
                    jinja2_templates.c.name,
                    jinja2_templates.c.content,
                )
                .select_from(products_to_templates.join(jinja2_templates))
                .where(products_to_templates.c.product_name == product_name)
            ):
                yield row
