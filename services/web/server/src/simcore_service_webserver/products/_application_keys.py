"""Keys to access web.Application's state"""

from typing import Final

from aiohttp import web
from models_library.products import ProductName

from ._models import Product, ProductBaseUrl

PRODUCTS_APPKEY: Final = web.AppKey("PRODUCTS_APPKEY", dict[ProductName, Product])
PRODUCTS_URL_MAPPING_APPKEY: Final = web.AppKey(
    "PRODUCTS_URL_MAPPING_APPKEY", dict[ProductName, ProductBaseUrl]
)


DEFAULT_PRODUCT_APPKEY: Final = web.AppKey("DEFAULT_PRODUCT_APPKEY", ProductName)
