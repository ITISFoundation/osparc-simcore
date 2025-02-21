from pathlib import Path

import aiofiles
from aiohttp import web
from models_library.products import ProductName
from simcore_postgres_database.utils_products_prices import ProductPriceInfo

from .._constants import RQ_PRODUCT_KEY
from .._resources import webserver_resources
from . import _service
from ._web_events import APP_PRODUCTS_TEMPLATES_DIR_KEY
from .products_models import Product


def get_product_name(request: web.Request) -> str:
    """Returns product name in request but might be undefined"""
    product_name: str = request[RQ_PRODUCT_KEY]
    return product_name


def get_current_product(request: web.Request) -> Product:
    """Returns product associated to current request"""
    product_name: ProductName = get_product_name(request)
    current_product: Product = _service.get_product(
        request.app, product_name=product_name
    )
    return current_product


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


def _safe_get_current_product(request: web.Request) -> Product | None:
    try:
        product: Product = get_current_product(request)
        return product
    except KeyError:
        return None


async def get_product_template_path(request: web.Request, filename: str) -> Path:
    if product := _safe_get_current_product(request):
        if template_name := product.get_template_name_for(filename):
            template_dir: Path = request.app[APP_PRODUCTS_TEMPLATES_DIR_KEY]
            template_path = template_dir / template_name
            if not template_path.exists():
                # cache
                content = await _service.get_template_content(
                    request.app, template_name=template_name
                )
                try:
                    async with aiofiles.open(template_path, "w") as fh:
                        await fh.write(content)
                except Exception:
                    # fails to write
                    if template_path.exists():
                        template_path.unlink()
                    raise

            return template_path

        # check static resources under templates/
        if (
            template_path := _themed(f"templates/{product.name}", filename)
        ) and template_path.exists():
            return template_path

    # If no product or template for product defined, we fall back to common templates
    common_template = _themed("templates/common", filename)
    if not common_template.exists():
        msg = f"{filename} is not part of the templates/common"
        raise ValueError(msg)

    return common_template
