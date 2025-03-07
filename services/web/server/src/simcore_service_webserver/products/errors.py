from ..errors import WebServerBaseError


class ProductError(WebServerBaseError, ValueError): ...


class ProductNotFoundError(ProductError):
    msg_template = "Undefined product '{product_name}'"


class ProductPriceNotDefinedError(ProductError):
    msg_template = "Product price not defined. {reason}"


class BelowMinimumPaymentError(ProductError):
    msg_template = "Payment of {amount_usd} USD is below the required minimum of {min_payment_amount_usd} USD"


class ProductTemplateNotFoundError(ProductError):
    msg_template = "Missing template {template_name} for product"


class MissingStripeConfigError(ProductError):
    msg_template = "Missing product stripe for product {product_name}"
