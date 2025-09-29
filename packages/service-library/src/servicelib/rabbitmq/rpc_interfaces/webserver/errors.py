from ..._errors import RPCInterfaceError


class ProjectNotFoundRpcError(  # pylint: disable=too-many-ancestors
    RPCInterfaceError
): ...


class ProjectForbiddenRpcError(  # pylint: disable=too-many-ancestors
    RPCInterfaceError
): ...
