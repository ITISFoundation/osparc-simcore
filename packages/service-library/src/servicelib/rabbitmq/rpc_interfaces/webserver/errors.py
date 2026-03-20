from ..._errors import RPCInterfaceError


class ProjectNotFoundRpcError(  # pylint: disable=too-many-ancestors
    RPCInterfaceError
): ...


class ProjectForbiddenRpcError(  # pylint: disable=too-many-ancestors
    RPCInterfaceError
): ...


class NodeNotFoundRpcError(  # pylint: disable=too-many-ancestors
    RPCInterfaceError
): ...
