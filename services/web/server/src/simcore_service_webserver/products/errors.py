"""
    API plugin errors
"""


from ..errors import WebServerBaseError


class ProductError(WebServerBaseError, ValueError):
    ...


class ProductPriceNotDefinedError(ProductError):
    msg_template = "Product price not defined. {reason}"
