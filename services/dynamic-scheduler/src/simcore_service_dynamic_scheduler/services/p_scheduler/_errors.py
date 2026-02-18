from common_library.errors_classes import OsparcErrorMixin


class _BasePSchedulerError(OsparcErrorMixin, Exception):
    """base exception for this module"""


class RunAlreadyExistsError(_BasePSchedulerError):
    msg_template: str = "A Run for node_id='{node_id}' already exists"
