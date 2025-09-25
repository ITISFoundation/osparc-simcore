"""Keys to access web.Application's state"""

from typing import Final

from aiohttp import web
from models_library.products import ProductName

from ._models import Product

APP_PRODUCTS_KEY: Final = web.AppKey("APP_PRODUCTS_KEY", dict[ProductName, Product])

APP_PRODUCTS_KEY_DEFAULT: Final = web.AppKey("_APP_PRODUCTS_KEY_DEFAULT", ProductName)
