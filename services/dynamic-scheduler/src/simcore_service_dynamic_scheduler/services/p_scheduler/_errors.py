from common_library.errors_classes import OsparcErrorMixin

from ._models import StepState


class _BasePSchedulerError(OsparcErrorMixin, Exception):
    """base exception for this module"""


class NoRunFoundError(_BasePSchedulerError):
    msg_template: str = "No active run found for node_id='{node_id}'"


class RunNotWaitingManualInterventionError(_BasePSchedulerError):
    msg_template: str = "run_id='{run_id}' is not waiting for manual intervention"


class StepNotFoundError(_BasePSchedulerError):
    msg_template: str = "step_id='{step_id}' was not found"


class RunAlreadyExistsError(_BasePSchedulerError):
    msg_template: str = "A Run for node_id='{node_id}' already exists"


class StepNotInFailedError(_BasePSchedulerError):
    msg_template: str = f"step_id='{{step_id}}' was not found or it's state!='{StepState.FAILED}'"
