from pydantic.errors import PydanticErrorMixin


class _OsparcErrorMixin(PydanticErrorMixin):
    @classmethod
    def get_full_class_name(cls) -> str:
        relevant_classes = [
            c.__name__
            for c in cls.__mro__[:-1]
            if c.__name__ not in ("PydanticErrorMixin", "_OsparcErrorMixin")
        ]
        return ".".join(reversed(relevant_classes))


class OsparcBaseError(_OsparcErrorMixin):
    ...
