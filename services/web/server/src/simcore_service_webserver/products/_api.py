from pathlib import Path

import aiofiles
from aiohttp import web
from models_library.products import ProductName

from .._constants import APP_PRODUCTS_KEY, RQ_PRODUCT_KEY
from .._resources import webserver_resources
from ._db import ProductRepository
from ._events import APP_PRODUCTS_TEMPLATES_DIR_KEY
from ._model import Product


def get_product_name(request: web.Request) -> str:
    product_name: str = request[RQ_PRODUCT_KEY]
    return product_name


def get_current_product(request: web.Request) -> Product:
    """Returns product associated to current request"""
    product_name: ProductName = get_product_name(request)
    current_product: Product = request.app[APP_PRODUCTS_KEY][product_name]
    return current_product


def list_products(app: web.Application) -> list[Product]:
    products: list[Product] = app[APP_PRODUCTS_KEY].values()
    return products


#
# helpers for get_product_template_path
#


def _themed(dirname: str, template: str) -> Path:
    path: Path = webserver_resources.get_path(f"{Path(dirname) / template}")
    return path


async def _get_content(request: web.Request, template_name: str):
    repo = ProductRepository(request)
    content = await repo.get_template_content(template_name)
    if not content:
        msg = f"Missing template {template_name} for product"
        raise ValueError(msg)
    return content


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
                content = await _get_content(request, template_name)
                try:
                    async with aiofiles.open(template_path, "wt") as fh:
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
