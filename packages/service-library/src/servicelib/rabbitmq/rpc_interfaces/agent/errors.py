from common_library.errors_classes import OsparcErrorMixin


class BaseAgentRPCError(OsparcErrorMixin, Exception):
    ...


class NoServiceVolumesFoundRPCError(BaseAgentRPCError):
    msg_template: str = (
        "Could not detect any unused volumes after waiting '{period}' seconds for "
        "volumes to be released after closing all container for service='{node_id}'"
    )
