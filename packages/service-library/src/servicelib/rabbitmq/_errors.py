from typing import Final

from common_library.errors_classes import OsparcErrorMixin

_ERROR_PREFIX: Final[str] = "rabbitmq_error"


class BaseRPCError(OsparcErrorMixin, RuntimeError): ...


class RPCNotInitializedError(BaseRPCError):
    code = f"{_ERROR_PREFIX}.not_started"  # type: ignore[assignment]
    msg_template = "Please check that the RabbitMQ RPC backend was initialized!"


class RemoteMethodNotRegisteredError(BaseRPCError):
    # TODO: this is an issue since some services relied on this error
    # faststream does not expose such an error
    # the only thing that happens is a timeout, which can be very long, but it's the only way to figure out if remote is not ther
    # TODO: check if any arguments help with this, but I doubt they do
    code = f"{_ERROR_PREFIX}.remote_not_registered"  # type: ignore[assignment]
    msg_template = (
        "Could not find a remote method named: '{method_name}'. "
        "Message from remote server was returned: {incoming_message}. "
    )


class RPCServerError(BaseRPCError):
    msg_template = (
        "While running method '{method_name}' raised "
        "'{exc_type}': '{exc_message}'\n{traceback}"
    )


class RPCInterfaceError(RPCServerError):
    """
    Base class for RPC interface exceptions.

    Avoid using domain exceptions directly; if a one-to-one mapping is required,
    prefer using the `from_domain_error` transformation function.
    """

    msg_template = "{domain_error_message} [{domain_error_code}]"

    @classmethod
    def from_domain_error(cls, err: OsparcErrorMixin):
        domain_err_ctx = err.error_context()
        return cls(
            domain_error_message=domain_err_ctx.pop("message"),
            domain_error_code=domain_err_ctx.pop("code"),
            **domain_err_ctx,  # same context as domain
        )
