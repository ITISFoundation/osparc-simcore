from pydantic.errors import PydanticErrorMixin


class _BaseAppError(PydanticErrorMixin, ValueError):
    @classmethod
    def get_full_class_name(cls) -> str:
        # Can be used as unique code identifier
        return f"{cls.__module__}.{cls.__name__}"


#
# gateway  errors
#


class PaymentsGatewayError(_BaseAppError):
    ...


class PaymentsGatewayNotReadyError(PaymentsGatewayError):
    msg_template = "Payments-Gateway is unresponsive: {checks}"


#
# stripe  errors
#


class StripeRuntimeError(_BaseAppError):
    msg_template = "Stripe unexpected error"
