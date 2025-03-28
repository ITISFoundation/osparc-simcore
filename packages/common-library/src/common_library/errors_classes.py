from typing import Any

from pydantic.errors import PydanticErrorMixin

from .error_codes import create_error_code


class _DefaultDict(dict):
    def __missing__(self, key):
        return f"'{key}=?'"


class OsparcErrorMixin(PydanticErrorMixin):
    code: str  # type: ignore[assignment]
    msg_template: str

    def __new__(cls, *_args, **_kwargs):
        if not hasattr(cls, "code"):
            cls.code = cls._get_full_class_name()
        return super().__new__(cls)

    def __init__(self, **ctx: Any) -> None:
        self.__dict__ = ctx
        super().__init__(message=self._build_message(), code=self.code)  # type: ignore[arg-type]

    def __str__(self) -> str:
        return self._build_message()

    def _build_message(self) -> str:
        # NOTE: safe. Does not raise KeyError
        return self.msg_template.format_map(_DefaultDict(**self.__dict__))

    @classmethod
    def _get_full_class_name(cls) -> str:
        relevant_classes = [
            c.__name__
            for c in cls.__mro__[:-1]
            if c.__name__
            not in (
                "PydanticErrorMixin",
                "OsparcErrorMixin",
                "Exception",
                "BaseException",
            )
        ]
        return ".".join(reversed(relevant_classes))

    def error_context(self) -> dict[str, Any]:
        """Returns context in which error occurred and stored within the exception"""
        return dict(**self.__dict__)

    def error_code(self) -> str:
        assert isinstance(self, Exception), "subclass must be exception"  # nosec
        return create_error_code(self)


class NotFoundError(OsparcErrorMixin):
    msg_template = "{resource} not found: id='{resource_id}'"


class ForbiddenError(OsparcErrorMixin):
    msg_template = "Access to {resource} is forbidden: id='{resource_id}'"


def make_resource_error(
    resource: str,
    error_cls: type[OsparcErrorMixin],
    base_exception: type[Exception] = Exception,
) -> type[OsparcErrorMixin]:
    class _ResourceError(error_cls, base_exception):
        def __init__(self, **ctx: Any):
            ctx.setdefault("resource", resource)
            # guesses identifer e.g. project_id, user_id
            if resource_id := ctx.get(f"{resource.lower()}_id"):
                ctx.setdefault("resource_id", resource_id)

            super().__init__(**ctx)

    resource_class_name = "".join(word.capitalize() for word in resource.split("_"))
    _ResourceError.__name__ = f"{resource_class_name}{error_cls.__name__}"
    return _ResourceError
