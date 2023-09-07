from aiohttp import web
from pydantic.errors import PydanticErrorMixin


class PaymentsErrors(PydanticErrorMixin, ValueError):
    to_status_code: int | None = None


class PaymentNotFoundError(PaymentsErrors):
    msg_template = "Invalid payment identifier '{payment_id}'"


class PaymentCompletedError(PaymentsErrors):
    msg_template = "Cannot complete payment '{payment_id}' that was already closed"


class PaymentUniqueViolationError(PaymentsErrors):
    msg_template = "Payment transaction '{payment_id}' aready exists"


maps_to_http: dict[int, list[type[PaymentsErrors]]] = {
    web.HTTPConflict.status_code: [
        PaymentUniqueViolationError,
        PaymentCompletedError,
    ],
    web.HTTPNotFound.status_code: [
        PaymentNotFoundError,
    ],
}
