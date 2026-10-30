from ..._errors import RPCInterfaceError


class BaseRpcError(RPCInterfaceError):  # pylint: disable=too-many-ancestors
    pass


class ComputationRunStatesRetrievalError(BaseRpcError):  # pylint: disable=too-many-ancestors
    msg_template = "Could not retrieve computation states from director-v2"


class ComputationalTaskMissingError(BaseRpcError):  # pylint: disable=too-many-ancestors
    msg_template = "Computational run not found for project {project_id}"


class EC2InstanceTypeNotFoundRPCError(BaseRpcError):  # pylint: disable=too-many-ancestors
    msg_template = "None of the EC2 instance types {ec2_types} is known to the clusters-keeper"


class ClustersKeeperNotAvailableRPCError(BaseRpcError):  # pylint: disable=too-many-ancestors
    msg_template = "The clusters-keeper service is currently unavailable"


class MultiContainerOverrideNotSupportedRPCError(BaseRpcError):  # pylint: disable=too-many-ancestors
    msg_template = (
        "Sizing the containers of a multi-container service {sub_service_names} from an EC2 "
        "machine type is not implemented"
    )


class UnsupportedNodeClassRPCError(BaseRpcError):  # pylint: disable=too-many-ancestors
    msg_template = (
        "The resources of service '{service_key}:{service_version}' cannot be derived from an EC2 machine type"
    )
