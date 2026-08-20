from ..._errors import RPCInterfaceError


class BaseRpcError(RPCInterfaceError):  # pylint: disable=too-many-ancestors
    pass


class ComputationRunStatesRetrievalError(BaseRpcError):  # pylint: disable=too-many-ancestors
    msg_template = "Could not retrieve computation states from director-v2"


class ComputationalTaskMissingError(BaseRpcError):  # pylint: disable=too-many-ancestors
    msg_template = "Computational run not found for project {project_id}"
