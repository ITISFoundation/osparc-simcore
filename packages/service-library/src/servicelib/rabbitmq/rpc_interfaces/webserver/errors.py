from common_library.errors_classes import (
    OsparcErrorMixin,
)


class WebServerRpcError(OsparcErrorMixin, Exception):
    msg_template = "{details}"

    @classmethod
    def from_domain_error(cls, err: OsparcErrorMixin):
        return cls(details=f"{err} [{err.__class__.__name__}]", **err.error_context())


class ProjectNotFoundRpcError(WebServerRpcError): ...


class ProjectForbiddenRpcError(WebServerRpcError): ...
