from typing import Any, Final

from pydantic.errors import PydanticErrorMixin

from .error_codes import create_error_code

# NOTE: guards against runaway messages (e.g. a large batch of errors, or an
# accidentally embedded traceback/blob) blowing up log lines beyond what
# log aggregators (Loki, journald, etc.) can reasonably handle.
_MAX_MESSAGE_LENGTH: Final[int] = 2000


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

    def __repr__(self) -> str:
        # NOTE: Exception.__repr__ (the default) shows `ClassName(*self.args)`.
        # Since OsparcErrorMixin/PydanticErrorMixin never populate `args`, that
        # default repr is always the useless, information-less `ClassName()`.
        # This matters because containers (list/tuple/dict) format their items
        # using repr(), not str() -- e.g. when an error ends up nested inside
        # another error's msg_template context. Overriding __repr__ here keeps
        # the actual message visible in those cases too.
        return f"{type(self).__name__}({self._build_message()!r})"

    def _build_message(self) -> str:
        # NOTE: safe. Does not raise KeyError
        message = self.msg_template.format_map(_DefaultDict(**self.__dict__))
        if len(message) > _MAX_MESSAGE_LENGTH:
            omitted = len(message) - _MAX_MESSAGE_LENGTH
            message = f"{message[:_MAX_MESSAGE_LENGTH]}... [truncated, {omitted} more chars]"
        return message

    @classmethod
    def _get_full_class_name(cls) -> str:
        relevant_classes = [
            c.__name__
            for c in cls.__mro__[:-1]
            if c.__name__
            not in {
                "PydanticErrorMixin",
                "OsparcErrorMixin",
                "Exception",
                "BaseException",
            }
        ]
        return ".".join(reversed(relevant_classes))

    def error_context(self) -> dict[str, Any]:
        """Returns context in which error occurred and stored within the exception"""
        return dict(**self.__dict__)

    def get_or_create_error_code(self) -> str:
        assert isinstance(self, Exception), "subclass must be exception"  # nosec
        return self.error_context().get("error_code") or create_error_code(self)
