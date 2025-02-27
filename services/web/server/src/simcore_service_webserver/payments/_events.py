"""
    Plugin to interact with the 'payments' service
"""

import logging

from aiohttp import web

from ..products import products_service
from ..products.errors import BelowMinimumPaymentError
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)


async def validate_prices_in_product_settings_on_startup(app: web.Application):
    payment_settings = get_plugin_settings(app)

    for product in products_service.list_products(app):
        if product.min_payment_amount_usd is not None:
            if (
                product.min_payment_amount_usd
                > payment_settings.PAYMENTS_AUTORECHARGE_DEFAULT_TOP_UP_AMOUNT
            ):
                raise BelowMinimumPaymentError(
                    amount_usd=payment_settings.PAYMENTS_AUTORECHARGE_DEFAULT_TOP_UP_AMOUNT,
                    min_payment_amount_usd=product.min_payment_amount_usd,
                )
            assert (  # nosec
                payment_settings.PAYMENTS_AUTORECHARGE_DEFAULT_MONTHLY_LIMIT is not None
            )
            if (
                product.min_payment_amount_usd
                > payment_settings.PAYMENTS_AUTORECHARGE_DEFAULT_MONTHLY_LIMIT
            ):
                raise BelowMinimumPaymentError(
                    amount_usd=payment_settings.PAYMENTS_AUTORECHARGE_DEFAULT_MONTHLY_LIMIT,
                    min_payment_amount_usd=product.min_payment_amount_usd,
                )
