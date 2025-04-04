from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State

from .products import ProductsRepository


async def setup_repository(app: FastAPI) -> AsyncIterator[State]:
    repo = ProductsRepository(db_engine=app.state.engine)

    yield {"default_product_name": await repo.get_default_product_name()}
