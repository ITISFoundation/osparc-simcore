import sqlalchemy as sa
from models_library.products import ProductName
from models_library.users import GroupID, UserID
from simcore_postgres_database.models.jinja2_templates import jinja2_templates
from simcore_postgres_database.models.users import users
from sqlalchemy.ext.asyncio import AsyncEngine


class BaseDataRepo:
    def __init__(self, db_engine: AsyncEngine):
        assert db_engine is not None  # nosec
        self.db_engine = db_engine

    async def _get(self, query):
        async with self.db_engine.begin() as conn:
            result = await conn.execute(query)
            return result.first()


class UserDataRepo(BaseDataRepo):
    async def get_primary_group_id(self, user_id: UserID) -> GroupID:
        if row := await self._get(
            sa.select(
                users.c.primary_gid,
            ).where(users.c.id == user_id)
        ):
            return GroupID(row.primary_gid)

        msg = f"{user_id=} not found"
        raise ValueError(msg)


class TemplatesRepo(BaseDataRepo):
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
