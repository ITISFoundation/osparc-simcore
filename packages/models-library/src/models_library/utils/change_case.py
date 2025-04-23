"""String convesion


Example of usage in pydantic:

[...]
    model_config = ConfigDict(
        alias_generator=snake_to_camel, # <-- note
    )

"""

# Partially taken from  https://github.com/autoferrit/python-change-case/blob/master/change_case/change_case.py#L131
import re
from typing import Final

_UNDERSCORER1: Final = re.compile(r"(.)([A-Z][a-z]+)")
_UNDERSCORER2: Final = re.compile(r"([a-z0-9])([A-Z])")


def snake_to_camel(subject: str) -> str:
    """
    WARNING: assumes 'subject' is snake!
    The algorithm does not check if the subject is already camelcase.
    Make sure that is the case, otherwise you might get conversions like "camelAlready" -> "camelalready"

    SEE test_utils_change_case.py
    """
    parts = subject.lower().split("_")
    return parts[0] + "".join(word.title() for word in parts[1:])


def snake_to_upper_camel(subject: str) -> str:
    """
    WARNING: assumes 'subject' is snake! See details on the implications above.
    """
    parts = subject.lower().split("_")
    return "".join(word.title() for word in parts)


def camel_to_snake(subject: str) -> str:
    subbed = _UNDERSCORER1.sub(r"\1_\2", subject)
    return _UNDERSCORER2.sub(r"\1_\2", subbed).lower()
