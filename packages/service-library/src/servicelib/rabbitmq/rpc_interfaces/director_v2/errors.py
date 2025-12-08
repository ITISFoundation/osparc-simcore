from ..._errors import RPCInterfaceError


class BaseRpcError(RPCInterfaceError):  # pylint: disable=too-many-ancestors
    pass


class ComputationalTaskMissingError(BaseRpcError):  # pylint: disable=too-many-ancestors
    msg_template = "Computational run not found for project {project_id}"
