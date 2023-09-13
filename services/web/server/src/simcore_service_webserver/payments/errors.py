from pydantic.errors import PydanticErrorMixin


class PaymentsErrors(PydanticErrorMixin, ValueError):
    ...


class PaymentNotFoundError(PaymentsErrors):
    msg_template = "Invalid payment identifier '{payment_id}'"


class PaymentCompletedError(PaymentsErrors):
    msg_template = "Cannot complete payment '{payment_id}' that was already closed"


class PaymentUniqueViolationError(PaymentsErrors):
    msg_template = "Payment transaction '{payment_id}' aready exists"
