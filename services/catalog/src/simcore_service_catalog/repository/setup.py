from fastapi import FastAPI

from .products import ProductsRepository


async def setup_repository(app: FastAPI):
    repo = ProductsRepository(db_engine=app.state.engine)
    app.state.default_product_name = await repo.get_default_product_name()
