from typing import Any, Callable

from fastapi import Depends, FastAPI, Request
from simcore_postgres_database.utils_products import get_default_product_name

from ...core.settings import ApplicationSettings


def get_reverse_url_mapper(request: Request) -> Callable[..., str]:
    def _reverse_url_mapper(name: str, **path_params: Any) -> str:
        url: str = request.url_for(name, **path_params)
        return url

    return _reverse_url_mapper


def get_settings(request: Request) -> ApplicationSettings:
    settings = request.app.state.settings
    assert isinstance(settings, ApplicationSettings)  # nosec
    return settings


def get_app(request: Request) -> FastAPI:
    return request.app


async def get_product_name(app: FastAPI = Depends(get_app)) -> str:
    if not hasattr(app.state, "default_product_name"):
        # lazy evaluation
        async with app.state.engine.acquire() as conn:
            app.state.default_product_name = await get_default_product_name(conn)

    default_product_name = app.state.default_product_name
    assert isinstance(default_product_name, str)  # nosec
    return default_product_name
