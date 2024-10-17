from common_library.errors_classes import OsparcErrorMixin


class _BaseRpcApiError(OsparcErrorMixin, ValueError):
    @classmethod
    def get_full_class_name(cls) -> str:
        # Can be used as unique code identifier
        return f"{cls.__module__}.{cls.__name__}"


#
# service-wide errors
#


class PaymentServiceUnavailableError(_BaseRpcApiError):
    msg_template = "Payments are currently unavailable: {human_readable_detail}"


#
# payment transactions errors
#


class PaymentsError(_BaseRpcApiError):
    msg_template = "Error in payment transaction '{payment_id}'"


class PaymentNotFoundError(PaymentsError):
    msg_template = "Payment transaction '{payment_id}' was not found"


class PaymentAlreadyExistsError(PaymentsError):
    msg_template = "Payment transaction '{payment_id}' was already initialized"


class PaymentAlreadyAckedError(PaymentsError):
    msg_template = "Payment transaction '{payment_id}' cannot be changes since it was already closed."


#
# payment-methods errors
#


class PaymentsMethodsError(_BaseRpcApiError):
    ...


class PaymentMethodNotFoundError(PaymentsMethodsError):
    msg_template = "The specified payment method '{payment_method_id}' does not exist"


class PaymentMethodAlreadyAckedError(PaymentsMethodsError):
    msg_template = (
        "Cannot create payment-method '{payment_method_id}' since it was already closed"
    )


class PaymentMethodUniqueViolationError(PaymentsMethodsError):
    msg_template = "Payment method '{payment_method_id}' aready exists"


class InvalidPaymentMethodError(PaymentsMethodsError):
    msg_template = "Invalid payment method '{payment_method_id}'"
