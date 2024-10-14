from pydantic.errors import PydanticErrorMixin


class BaseAgentRPCError(PydanticErrorMixin, Exception):
    ...


class NoServiceVolumesFoundRPCError(BaseAgentRPCError):
    msg_template: str = (
        "Could not detect any unused volumes after waiting '{period}' seconds for "
        "volumes to be released after closing all container for service='{node_id}'"
    )
