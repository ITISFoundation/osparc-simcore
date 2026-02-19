from common_library.errors_classes import OsparcErrorMixin

from ._models import StepState


class _BasePSchedulerError(OsparcErrorMixin, Exception):
    """base exception for this module"""


class RunAlreadyExistsError(_BasePSchedulerError):
    msg_template: str = "A Run for node_id='{node_id}' already exists"


class StepNotInFailedError(_BasePSchedulerError):
    msg_template: str = f"step_id='{{step_id}}' was not found or it's state!='{StepState.FAILED}'"


class StepNotFoundError(_BasePSchedulerError):
    msg_template: str = "step_id='{step_id}' was not found"
