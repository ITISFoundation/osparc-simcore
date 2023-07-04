from typing import Annotated

from fastapi import Depends, FastAPI, Request
from servicelib.fastapi.dependencies import get_app, get_reverse_url_mapper
from simcore_postgres_database.utils_products import get_default_product_name

from ...core.settings import ApplicationSettings


def get_settings(request: Request) -> ApplicationSettings:
    settings = request.app.state.settings
    assert isinstance(settings, ApplicationSettings)  # nosec
    return settings


async def get_product_name(app: Annotated[FastAPI, Depends(get_app)]) -> str:
    if not hasattr(app.state, "default_product_name"):
        # lazy evaluation
        async with app.state.engine.acquire() as conn:
            app.state.default_product_name = await get_default_product_name(conn)

    default_product_name = app.state.default_product_name
    assert isinstance(default_product_name, str)  # nosec
    return default_product_name


assert get_reverse_url_mapper  # nosec
assert get_app  # nosec

__all__: tuple[str, ...] = (
    "get_reverse_url_mapper",
    "get_app",
)
