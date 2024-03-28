"""
    Plugin to interact with the 'payments' service
"""

import logging

from aiohttp import web

from ..products.api import list_products
from ..products.errors import BelowMinimumPaymentError
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)


async def validate_prices_in_product_settings_on_startup(app: web.Application):
    payment_settings = get_plugin_settings(app)

    for product in list_products(app):
        if product.min_payment_amount_usd is not None:
            if (
                product.min_payment_amount_usd
                > payment_settings.PAYMENTS_AUTORECHARGE_DEFAULT_TOP_UP_AMOUNT
            ):
                raise BelowMinimumPaymentError(
                    amount_usd=payment_settings.PAYMENTS_AUTORECHARGE_DEFAULT_TOP_UP_AMOUNT,
                    min_payment_amount_usd=product.min_payment_amount_usd,
                )
            if (
                product.min_payment_amount_usd
                > payment_settings.PAYMENTS_AUTORECHARGE_DEFAULT_MONTHLY_LIMIT
            ):
                raise BelowMinimumPaymentError(
                    amount_usd=payment_settings.PAYMENTS_AUTORECHARGE_DEFAULT_MONTHLY_LIMIT,
                    min_payment_amount_usd=product.min_payment_amount_usd,
                )
