from pydantic.errors import PydanticErrorMixin


class PaymentsError(PydanticErrorMixin, ValueError):
    ...


class PaymentNotFoundError(PaymentsError):
    msg_template = "Invalid payment identifier '{payment_id}'"


class PaymentCompletedError(PaymentsError):
    msg_template = "Cannot complete payment '{payment_id}' that was already closed"


class PaymentUniqueViolationError(PaymentsError):
    msg_template = "Payment transaction '{payment_id}' aready exists"


#
# payment methods
#


class PaymentsMethodsError(PydanticErrorMixin, ValueError):
    ...


class PaymentMethodNotFoundError(PaymentsMethodsError):
    msg_template = "Cannot find payment method '{payment_method_id}'"


class PaymentMethodAlreadyAckedError(PaymentsMethodsError):
    msg_template = (
        "Cannot create payment-method '{payment_method_id}' since it was already closed"
    )


class PaymentMethodUniqueViolationError(PaymentsMethodsError):
    msg_template = "Payment method '{payment_method_id}' aready exists"
