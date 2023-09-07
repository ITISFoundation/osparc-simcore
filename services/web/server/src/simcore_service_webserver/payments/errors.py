from pydantic.errors import PydanticErrorMixin


class PaymentsErrors(PydanticErrorMixin, ValueError):
    ...


class PaymentNotFoundError(PaymentsErrors):
    msg_template = "Invalid payment identifier {payment_id!r}"
