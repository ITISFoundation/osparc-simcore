from typing import Final

from pydantic.errors import PydanticErrorMixin

_ERROR_PREFIX: Final[str] = "rabbitmq.robust_rpc."


class BaseRPCError(PydanticErrorMixin, RuntimeError):
    ...


class RPCNotInitializedError(BaseRPCError):
    code = f"{_ERROR_PREFIX}.not_started"
    msg_template = "Please check that the RPC backend was initialized!"


class RemoteMethodNotRegisteredError(BaseRPCError):
    code = f"{_ERROR_PREFIX}.remote_not_registered"
    msg_template = (
        "Could not find a remote method named: '{method_name}'. "
        "Message from remote server was returned: {incoming_message}. "
    )
