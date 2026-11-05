from common_library.errors_classes import OsparcErrorMixin


class BaseSchedulerError(OsparcErrorMixin, RuntimeError): ...


class WorkflowNotFoundError(BaseSchedulerError):
    msg_template = "Workflow '{name}' not found. Available: {available}"


class WorkflowAlreadyRegisteredError(BaseSchedulerError):
    msg_template = "Workflow '{name}' is already registered"


class ActivityNotInFailedError(BaseSchedulerError):
    msg_template = (
        "Activity '{activity_name}' is not in failed_activities for workflow '{workflow_id}'. Failed: {failed}"
    )
