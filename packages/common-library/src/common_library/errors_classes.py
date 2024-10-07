from pydantic.errors import PydanticErrorMixin


class _DefaultDict(dict):
    def __missing__(self, key):
        return f"'{key}=?'"


class OsparcErrorMixin(PydanticErrorMixin):
    code: str   # type: ignore[assignment]
    msg_template: str

    def __new__(cls, *_args, **_kwargs):
        if not hasattr(cls, "code"):
            cls.code = cls._get_full_class_name()
        return super().__new__(cls)

    def __init__(self, *_args, **kwargs) -> None:
        self.__dict__ = kwargs
        super().__init__(message=self._build_message(), code=self.code) # type: ignore[arg-type]

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
