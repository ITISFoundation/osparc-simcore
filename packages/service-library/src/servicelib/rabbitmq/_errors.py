from typing import Final

from common_library.errors_classes import OsparcErrorMixin

_ERROR_PREFIX: Final[str] = "rabbitmq_error"


class BaseRPCError(OsparcErrorMixin, RuntimeError):
    ...


class RPCNotInitializedError(BaseRPCError):
    code = f"{_ERROR_PREFIX}.not_started"   # type: ignore[assignment]
    msg_template = "Please check that the RabbitMQ RPC backend was initialized!"


class RemoteMethodNotRegisteredError(BaseRPCError):
    code = f"{_ERROR_PREFIX}.remote_not_registered" # type: ignore[assignment]
    msg_template = (
        "Could not find a remote method named: '{method_name}'. "
        "Message from remote server was returned: {incoming_message}. "
    )


class RPCServerError(BaseRPCError):
    msg_template = (
        "While running method '{method_name}' raised "
        "'{exc_type}': '{exc_message}'\n{traceback}"
    )
