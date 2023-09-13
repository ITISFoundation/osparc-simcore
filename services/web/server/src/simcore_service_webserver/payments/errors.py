from pydantic.errors import PydanticErrorMixin


class PaymentsErrors(PydanticErrorMixin, ValueError):
    ...


class PaymentNotFoundError(PaymentsErrors):
    msg_template = "Invalid payment identifier '{payment_id}'"


class PaymentCompletedError(PaymentsErrors):
    msg_template = "Cannot complete payment '{payment_id}' that was already closed"


class PaymentUniqueViolationError(PaymentsErrors):
    msg_template = "Payment transaction '{payment_id}' aready exists"


#
# payment methods
#


class PaymentsMethodsErrors(PydanticErrorMixin, ValueError):
    ...


class PaymentMethodNotFoundError(PaymentsMethodsErrors):
    msg_template = "Cannot find payment method '{payment_method_id}'"


class PaymentMethodCompletedError(PaymentsMethodsErrors):
    msg_template = (
        "Cannot create payment-method '{payment_method_id}' since it was already closed"
    )


class PaymentMethodUniqueViolationError(PaymentsMethodsErrors):
    msg_template = "Payment method '{payment_method_id}' aready exists"
