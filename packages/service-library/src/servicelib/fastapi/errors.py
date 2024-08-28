from pydantic.v1.errors import PydanticErrorMixin


class ApplicationRuntimeError(PydanticErrorMixin, RuntimeError):
    pass


class ApplicationStateError(ApplicationRuntimeError):
    msg_template: str = "Invalid app.state.{state}: {msg}"
