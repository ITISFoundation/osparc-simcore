from pydantic.errors import PydanticErrorMixin


class OsparcErrorMixin(PydanticErrorMixin):
    """THE base class used for any custom exception in this repo"""

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

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "code"):
            cls.code = cls._get_full_class_name()
        return super().__new__(cls, *args, **kwargs)
