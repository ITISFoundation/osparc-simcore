from ..._errors import RPCInterfaceError


class BaseRpcError(RPCInterfaceError):  # pylint: disable=too-many-ancestors
    pass


class ComputationRunStatesRetrievalError(BaseRpcError):  # pylint: disable=too-many-ancestors
    msg_template = "Could not retrieve computation states from director-v2"


class ComputationalTaskMissingError(BaseRpcError):  # pylint: disable=too-many-ancestors
    msg_template = "Computational run not found for project {project_id}"


class InsufficientInstanceResourcesError(BaseRpcError):  # pylint: disable=too-many-ancestors
    msg_template = (
        "Machine with {instance_cpus} CPUs and {instance_ram} RAM is too small to run"
        " '{service_key}:{service_version}': only {cpus} CPUs and {ram} RAM would be left"
        " for the service after reserving what the dynamic-sidecar and its helper containers need"
    )
