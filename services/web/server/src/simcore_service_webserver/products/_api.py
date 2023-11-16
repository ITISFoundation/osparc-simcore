from decimal import Decimal
from pathlib import Path

import aiofiles
from aiohttp import web
from models_library.basic_types import NonNegativeDecimal
from models_library.products import CreditResultGet, ProductName

from .._constants import APP_PRODUCTS_KEY, RQ_PRODUCT_KEY
from .._resources import webserver_resources
from ._db import ProductRepository
from ._events import APP_PRODUCTS_TEMPLATES_DIR_KEY
from ._model import Product
from .errors import ProductPriceNotDefinedError


def get_product_name(request: web.Request) -> str:
    product_name: str = request[RQ_PRODUCT_KEY]
    return product_name


def get_product(app: web.Application, product_name: ProductName) -> Product:
    product: Product = app[APP_PRODUCTS_KEY][product_name]
    return product


def get_current_product(request: web.Request) -> Product:
    """Returns product associated to current request"""
    product_name: ProductName = get_product_name(request)
    current_product: Product = get_product(request.app, product_name=product_name)
    return current_product


def list_products(app: web.Application) -> list[Product]:
    products: list[Product] = list(app[APP_PRODUCTS_KEY].values())
    return products


async def get_current_product_credit_price(
    request: web.Request,
) -> NonNegativeDecimal | None:
    """Gets latest credit price for this product.

    NOTE: Contrary to other product api functions (e.g. get_current_product) this function
    gets the latest update from the database. Otherwise, products are loaded
    on startup and cached therefore in those cases would require a restart
    of the service for the latest changes to take effect.
    """
    current_product_name = get_product_name(request)
    repo = ProductRepository.create_from_request(request)
    return await repo.get_product_latest_credit_price_or_none(current_product_name)


async def get_credit_amount(
    app: web.Application, *, dollar_amount: Decimal, product_name: ProductName
) -> CreditResultGet:
    """For provided dollars and product gets credit amount.

    NOTE: Contrary to other product api functions (e.g. get_current_product) this function
    gets the latest update from the database. Otherwise, products are loaded
    on startup and cached therefore in those cases would require a restart
    of the service for the latest changes to take effect.
    """
    repo = ProductRepository.create_from_app(app)
    usd_per_credit: NonNegativeDecimal | None = (
        await repo.get_product_latest_credit_price_or_none(product_name)
    )
    if not usd_per_credit:
        # '0 or None' should raise
        raise ProductPriceNotDefinedError(
            reason=f"Product {product_name} usd_per_credit is either not defined or zero"
        )

    credit_amount = dollar_amount / usd_per_credit
    return CreditResultGet(product_name=product_name, credit_amount=credit_amount)


#
# helpers for get_product_template_path
#


def _themed(dirname: str, template: str) -> Path:
    path: Path = webserver_resources.get_path(f"{Path(dirname) / template}")
    return path


async def _get_content(request: web.Request, template_name: str):
    repo = ProductRepository.create_from_request(request)
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
