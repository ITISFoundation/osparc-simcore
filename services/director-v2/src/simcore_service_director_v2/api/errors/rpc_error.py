from common_library.errors_classes import OsparcErrorMixin


class BaseRpcError(OsparcErrorMixin, Exception):
    pass


class ComputationalTaskMissingError(BaseRpcError):
    msg_template = "Computational run not found for project {project_id}"
