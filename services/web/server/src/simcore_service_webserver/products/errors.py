from ..errors import WebServerBaseError


class ProductError(WebServerBaseError, ValueError): ...


class UnknownProductError(ProductError):
    msg_template = "Cannot determine which is the product in the current context"


class ProductNotFoundError(ProductError):
    msg_template = "Undefined product '{product_name}'"


class ProductPriceNotDefinedError(ProductError):
    msg_template = "Product price not defined: {details}"


class BelowMinimumPaymentError(ProductError):
    msg_template = "Payment of {amount_usd} USD is below the required minimum of {min_payment_amount_usd} USD"


class MissingStripeConfigError(ProductError):
    msg_template = (
        "Missing product stripe for product {product_name}.\n"
        "NOTE: This is currently setup manually by the operator in pg database via adminer and also in the stripe platform."
    )
