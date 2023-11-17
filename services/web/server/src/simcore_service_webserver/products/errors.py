"""
    API plugin errors
"""


from pydantic.errors import PydanticErrorMixin


class ProductError(PydanticErrorMixin, ValueError):
    ...


class ProductPriceNotDefinedError(ProductError):
    msg_template = "Product price not defined. {reason}"
