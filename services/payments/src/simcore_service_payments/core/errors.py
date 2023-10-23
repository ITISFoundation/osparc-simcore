from pydantic.errors import PydanticErrorMixin


class PaymentsValueError(PydanticErrorMixin, ValueError):
    msg_template = "Error in payment transaction '{payment_id}'"


class PaymentNotFoundError(PaymentsValueError):
    msg_template = "Payment transaction '{payment_id=}' was not found"


class PaymentAlreadyExistsError(PaymentsValueError):
    msg_template = "Payment transaction '{payment_id}' was already initialized"


class PaymentAlreadyClosedError(PaymentsValueError):
    msg_template = "Payment transaction '{payment_id}' cannot be changes since it was already closed."
