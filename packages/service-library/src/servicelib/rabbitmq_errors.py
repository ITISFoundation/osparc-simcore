from typing import Final

from pydantic.errors import PydanticErrorMixin

_ERROR_PREFIX: Final[str] = "rabbitmq_error"


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


class RPCNamespaceTooLongError(BaseRPCError):
    code = f"{_ERROR_PREFIX}.rpc_namespace_error"
    msg_template = (
        "The generated namespace {namespace} is too long. "
        "It contains {namespace_length} characters it is limited to {char_limit}."
    )


class RPCNamespaceInvalidCharsError(BaseRPCError):
    code = f"{_ERROR_PREFIX}.rpc_namespace_error"
    msg_template = (
        "Generated namespace {namespace} contains not allowed characters."
        "Allowed chars must match {match_regex}."
    )


class RPCHandlerNameTooLongError(BaseRPCError):
    code = f"{_ERROR_PREFIX}.namespaced_method_too_long"
    msg_template = (
        "The combined values of '{{namespace}}.{{method_name}}' "
        "must be less than 256 bytes. It is currently {length} bytes: "
        "{namespaced_method_name}"
    )
