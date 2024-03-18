"""
    API plugin errors
"""


from ..errors import WebServerBaseError


class ProductError(WebServerBaseError, ValueError):
    ...


class ProductPriceNotDefinedError(ProductError):
    msg_template = "Product price not defined. {reason}"


class BelowMinimumPaymentError(ProductError):
    msg_template = (
        "Payment of {amount_usd} is below the required minimum of {min_payment_amount_usd}. "
        "Please ensure the amount is at least the minimum required to proceed."
    )
