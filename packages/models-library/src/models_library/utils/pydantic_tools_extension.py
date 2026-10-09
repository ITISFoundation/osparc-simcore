from pydantic import TypeAdapter, ValidationError


def parse_obj_or_none[T](type_: type[T], obj) -> T | None:
    try:
        return TypeAdapter(type_).validate_python(obj)
    except ValidationError:
        return None
