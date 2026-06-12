import logging

from aiohttp import web
from models_library.products import ProductName
from models_library.users import UserID
from simcore_postgres_database.utils_products_prices import ProductPriceInfo

from ..constants import RQ_PRODUCT_KEY
from ..groups.groups_service import is_user_in_group
from . import _service
from .errors import UnknownProductError
from .models import Product

_logger = logging.getLogger(__name__)


def get_product_name(request: web.Request) -> str:
    """Returns product name in request but might be undefined"""
    # NOTE: introduced by middleware
    try:
        product_name: str = request[RQ_PRODUCT_KEY]
    except KeyError as exc:
        error = UnknownProductError(tip="Check products middleware")
        raise error from exc
    return product_name


def get_current_product(request: web.Request) -> Product:
    """Returns product associated to current request"""
    product_name: ProductName = get_product_name(request)
    current_product: Product = _service.get_product(request.app, product_name=product_name)
    return current_product


async def is_user_in_product_support_group(request: web.Request, *, user_id: UserID) -> bool:
    """Checks if the user belongs to the support group of the given product.
    If the product does not have a support group, returns False.
    """
    product = get_current_product(request)
    if product.support_standard_group_id is None:
        return False
    return await is_user_in_group(
        app=request.app,
        user_id=user_id,
        group_id=product.support_standard_group_id,
    )


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
    return await _service.get_credit_price_info(request.app, product_name=current_product_name)
