from pydantic.errors import PydanticErrorMixin


class DynamicSchedulerError(PydanticErrorMixin, ValueError):
    msg_template = "Error in dynamic schduler transaction"
