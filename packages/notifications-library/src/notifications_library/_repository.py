from collections.abc import AsyncIterable

import sqlalchemy as sa
from models_library.products import ProductName
from models_library.users import UserID
from simcore_postgres_database.models.jinja2_templates import jinja2_templates
from simcore_postgres_database.models.products_to_templates import products_to_templates
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.ext.asyncio import AsyncEngine

from ._models import (
    JinjaTemplateDbGet,
    UserData,
)


class _BaseRepo:
    def __init__(self, db_engine: AsyncEngine):
        assert db_engine is not None  # nosec
        self.db_engine = db_engine


class UsersRepo(_BaseRepo):
    async def get_user_data(self, user_id: UserID) -> UserData:
        query = sa.select(
            # NOTE: careful! privacy applies here!
            users.c.name,
            users.c.first_name,
            users.c.last_name,
            users.c.email,
        ).where(users.c.id == user_id)
        async with pass_or_acquire_connection(self.db_engine) as conn:
            result = await conn.execute(query)
            row = result.one_or_none()

        if row is None:
            msg = f"User not found {user_id=}"
            raise ValueError(msg)

        return UserData(
            user_name=row.name,
            first_name=row.first_name,
            last_name=row.last_name,
            email=row.email,
        )


class TemplatesRepo(_BaseRepo):
    async def iter_email_templates(
        self, product_name: ProductName
    ) -> AsyncIterable[JinjaTemplateDbGet]:
        async with pass_or_acquire_connection(self.db_engine) as conn:
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
                yield JinjaTemplateDbGet(
                    product_name=product_name, name=row.name, content=row.content
                )

    async def iter_product_templates(
        self, product_name: ProductName
    ) -> AsyncIterable[JinjaTemplateDbGet]:
        async with pass_or_acquire_connection(self.db_engine) as conn:
            async for row in await conn.stream(
                sa.select(
                    products_to_templates.c.product_name,
                    jinja2_templates.c.name,
                    jinja2_templates.c.content,
                )
                .select_from(products_to_templates.join(jinja2_templates))
                .where(products_to_templates.c.product_name == product_name)
            ):
                yield JinjaTemplateDbGet(
                    product_name=row.product_name, name=row.name, content=row.template
                )
