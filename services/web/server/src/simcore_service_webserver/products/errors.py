"""
    API plugin errors
"""


from ..errors import WebServerError


class ProductError(WebServerError, ValueError):
    ...


class ProductPriceNotDefinedError(ProductError):
    msg_template = "Product price not defined. {reason}"
