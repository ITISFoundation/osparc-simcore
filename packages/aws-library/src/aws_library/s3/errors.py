from pydantic.errors import PydanticErrorMixin


class S3RuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "S3 client unexpected error"


class S3NotConnectedError(S3RuntimeError):
    msg_template: str = "Cannot connect with s3 server"
