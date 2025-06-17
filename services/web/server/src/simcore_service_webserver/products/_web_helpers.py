import contextlib
from pathlib import Path

import aiofiles
from aiohttp import web
from models_library.products import ProductName
from simcore_postgres_database.utils_products_prices import ProductPriceInfo

from .._resources import webserver_resources
from ..constants import RQ_PRODUCT_KEY
from . import _service
from ._web_events import APP_PRODUCTS_TEMPLATES_DIR_KEY
from .errors import (
    FileTemplateNotFoundError,
    ProductNotFoundError,
    UnknownProductError,
)
from .models import Product


def get_product_name(request: web.Request) -> str:
    """Returns product name in request but might be undefined"""
    # NOTE: introduced by middleware
    try:
        product_name: str = request[RQ_PRODUCT_KEY]
    except KeyError as exc:
        error = UnknownProductError()
        error.add_note("TIP: Check products middleware")
        raise error from exc
    return product_name


def get_current_product(request: web.Request) -> Product:
    """Returns product associated to current request"""
    product_name: ProductName = get_product_name(request)
    current_product: Product = _service.get_product(
        request.app, product_name=product_name
    )
    return current_product


def _get_current_product_or_none(request: web.Request) -> Product | None:
    with contextlib.suppress(ProductNotFoundError, UnknownProductError):
        product: Product = get_current_product(request)
        return product
    return None


async def get_current_product_credit_price_info(
    request: web.Request,
) -> ProductPriceInfo | None:
    """Gets latest credit price for this product.

    NOTE: Contrary to other product api functions (e.g. get_current_product) this function
    gets the latest update from the database. Otherwise, products are loaded
    on startup and cached therefore in those cases would require a restart
    of the service for the latest changes to take effect.
    """
    current_product_name = get_product_name(request)
    return await _service.get_credit_price_info(
        request.app, product_name=current_product_name
    )


def _themed(dirname: str, template: str) -> Path:
    path: Path = webserver_resources.get_path(f"{Path(dirname) / template}")
    return path


async def _get_common_template_path(filename: str) -> Path:
    common_template = _themed("templates/common", filename)
    if not common_template.exists():
        raise FileTemplateNotFoundError(filename=filename)
    return common_template


async def _cache_template_content(
    request: web.Request, template_path: Path, template_name: str
) -> None:
    content = await _service.get_template_content(
        request.app, template_name=template_name
    )
    try:
        async with aiofiles.open(template_path, "w") as fh:
            await fh.write(content)
    except Exception:
        if template_path.exists():
            template_path.unlink()
        raise


async def _get_product_specific_template_path(
    request: web.Request, product: Product, filename: str
) -> Path | None:
    if template_name := product.get_template_name_for(filename):
        template_dir: Path = request.app[APP_PRODUCTS_TEMPLATES_DIR_KEY]
        template_path = template_dir / template_name
        if not template_path.exists():
            await _cache_template_content(request, template_path, template_name)
        return template_path

    template_path = _themed(f"templates/{product.name}", filename)
    if template_path.exists():
        return template_path

    return None


async def get_product_template_path(request: web.Request, filename: str) -> Path:
    if (product := _get_current_product_or_none(request)) and (
        template_path := await _get_product_specific_template_path(
            request, product, filename
        )
    ):
        return template_path

    return await _get_common_template_path(filename)
