from common_library.errors_classes import OsparcErrorMixin


class BaseRpcError(OsparcErrorMixin):
    pass


class ComputationalRunNotFoundError(BaseRpcError):
    msg_template = "Computational run not found for project {project_id}"
