from models_library.api_schemas_payments.errors import (
    InvalidPaymentMethodError,
    PaymentMethodAlreadyAckedError,
    PaymentMethodNotFoundError,
    PaymentMethodUniqueViolationError,
    PaymentNotFoundError,
    PaymentServiceUnavailableError,
)

from ..errors import WebServerBaseError

__all__ = (
    "InvalidPaymentMethodError",
    "PaymentMethodAlreadyAckedError",
    "PaymentMethodNotFoundError",
    "PaymentMethodUniqueViolationError",
    "PaymentNotFoundError",
    "PaymentServiceUnavailableError",
)


class PaymentsPluginError(WebServerBaseError, ValueError):
    ...


class PaymentCompletedError(PaymentsPluginError):
    msg_template = "Cannot complete payment '{payment_id}' that was already closed"


class PaymentUniqueViolationError(PaymentsPluginError):
    msg_template = "Payment transaction '{payment_id}' aready exists"
