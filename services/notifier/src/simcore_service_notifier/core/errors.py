from pydantic.errors import PydanticErrorMixin


class NotifierError(PydanticErrorMixin, ValueError):
    ...
