"""
    API plugin errors
"""


from ..errors import WebServerBaseError


class ProductError(WebServerBaseError, ValueError):
    ...


class ProductNotFoundError(ProductError):
    msg_template = "Undefined product '{product_name}'"


class ProductPriceNotDefinedError(ProductError):
    msg_template = "Product price not defined. {reason}"


class BelowMinimumPaymentError(ProductError):
    msg_template = "Payment of {amount_usd} USD is below the required minimum of {min_payment_amount_usd} USD"
