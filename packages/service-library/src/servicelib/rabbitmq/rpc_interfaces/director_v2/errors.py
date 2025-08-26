from ..._errors import RPCInterfaceError


class BaseRpcError(RPCInterfaceError):
    pass


class ComputationalTaskMissingError(BaseRpcError):
    msg_template = "Computational run not found for project {project_id}"
