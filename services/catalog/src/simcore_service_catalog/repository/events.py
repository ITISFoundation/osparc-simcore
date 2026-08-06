from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from sqlalchemy.ext.asyncio import AsyncEngine

from .products import ProductsRepository


async def _default_product_name_lifespan(app: FastAPI) -> AsyncIterator[State]:
    assert isinstance(app.state.engine, AsyncEngine)  # nosec

    repo = ProductsRepository(db_engine=app.state.engine)

    app.state.default_product_name = await repo.get_default_product_name()

    yield {}


def configure_default_product_name(app_lifespan: LifespanManager[FastAPI]) -> None:
    app_lifespan.add(_default_product_name_lifespan)
