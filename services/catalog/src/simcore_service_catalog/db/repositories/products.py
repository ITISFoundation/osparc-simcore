from simcore_postgres_database.utils_products import get_default_product_name

from ._base import BaseRepository


class ProductsRepository(BaseRepository):
    async def get_default_product_name(self) -> str:
        async with self.db_engine.begin() as conn:
            product_name: str = await get_default_product_name(conn)
            return product_name
