from pydantic.errors import PydanticErrorMixin


class EC2RuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "EC2 client unexpected error"
