from common_library.errors_classes import OsparcErrorMixin

from ..._errors import RPCServerError


class WebServerRpcError(RPCServerError):
    msg_template = "{domain_error_nessage} [{domain_error_type_name}]"

    @classmethod
    def from_domain_error(cls, err: OsparcErrorMixin):
        return cls(
            # composes a  message
            domain_error_nessage=err.message,
            domain_error_type_name=f"{err.__class__.__name__}",
            # copies context
            **err.error_context(),
        )


class ProjectNotFoundRpcError(WebServerRpcError): ...


class ProjectForbiddenRpcError(WebServerRpcError): ...
