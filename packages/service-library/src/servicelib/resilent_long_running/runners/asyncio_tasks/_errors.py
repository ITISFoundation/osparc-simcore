from common_library.errors_classes import OsparcErrorMixin


class BaseAsyncioTasksError(OsparcErrorMixin, Exception):
    pass


class HandlerAlreadyRegisteredError(BaseAsyncioTasksError):
    msg_template = (
        "a handler name='{name}' already exists. Please try to change its name"
    )


class HandlerNotRegisteredError(BaseAsyncioTasksError):
    msg_template = "a handler name='{name}' was not found"


class TaskNotFoundError(BaseAsyncioTasksError):
    msg_template = "no task found for unique_id='{unique_id}'"
