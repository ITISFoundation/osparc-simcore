"""Keys to access web.Application's state"""

from typing import Final

from aiohttp import web
from models_library.products import ProductName

from ._models import Product

PRODUCTS_APPKEY: Final = web.AppKey("PRODUCTS_APPKEY", dict[ProductName, Product])

DEFAULT_PRODUCT_APPKEY: Final = web.AppKey("DEFAULT_PRODUCT_APPKEY", ProductName)
