from ...core.errors import DirectorError


class OsparcVariableResolveError(DirectorError):
    msg_template: str = "Failed to resolve variable {variable_key!r} in handler {handler_name!r}"


class OsparcVariableResolveTimeoutError(OsparcVariableResolveError):
    msg_template: str = (
        "Timed out resolving variable {variable_key!r} in handler {handler_name!r} after {timeout_seconds}s"
    )
