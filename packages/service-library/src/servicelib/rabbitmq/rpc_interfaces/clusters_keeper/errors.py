from ..._errors import RPCInterfaceError


class BaseRpcError(RPCInterfaceError):  # pylint: disable=too-many-ancestors
    pass


class InvalidEC2InstanceTypesRPCError(BaseRpcError):  # pylint: disable=too-many-ancestors
    msg_template = "The clusters-keeper rejected the EC2 instance types {ec2_types} as invalid"
