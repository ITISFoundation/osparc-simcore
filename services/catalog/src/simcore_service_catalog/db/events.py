import logging

from fastapi import FastAPI

from .repositories.products import ProductsRepository

logger = logging.getLogger(__name__)


async def setup_default_product(app: FastAPI):
    repo = ProductsRepository(db_engine=app.state.engine)
    app.state.default_product_name = await repo.get_default_product_name()
