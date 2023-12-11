from models_library.api_schemas_payments.errors import BaseServiceError

#
# gateway  errors
#


class PaymentsGatewayError(BaseServiceError):
    ...


class PaymentsGatewayNotReadyError(PaymentsGatewayError):
    msg_template = "Payments-Gateway is unresponsive: {checks}"
