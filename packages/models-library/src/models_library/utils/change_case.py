""" String convesion


Example of usage in pydantic:

[...]
    class Config:
        extra = Extra.forbid
        alias_generator = snake_to_camel  # <--------
        json_loads = orjson.loads
        json_dumps = json_dumps

"""
# Partially taken from  https://github.com/autoferrit/python-change-case/blob/master/change_case/change_case.py#L131
import re

_underscorer1 = re.compile(r"(.)([A-Z][a-z]+)")
_underscorer2 = re.compile("([a-z0-9])([A-Z])")


def snake_to_camel(subject: str) -> str:
    """ """
    parts = subject.lower().split("_")
    return parts[0] + "".join(word.title() for word in parts[1:])


def snake_to_upper_camel(subject: str) -> str:
    parts = subject.lower().split("_")
    return "".join(word.title() for word in parts)


def camel_to_snake(subject: str) -> str:
    subbed = _underscorer1.sub(r"\1_\2", subject)
    return _underscorer2.sub(r"\1_\2", subbed).lower()
