import sys
from typing import Tuple


def get_args(annotation) -> Tuple:
    assert (  # nosec
        sys.version_info.major == 3 and sys.version_info.minor < 8  # nosec
    ), "TODO: py3.8 replace __args__ with typings.get_args"

    try:
        annotated_types = annotation.__args__  # works for unions
    except AttributeError:
        annotated_types = (annotation,)

    def _transform(annotated_type):
        for primitive_type in (float, bool, int, str):
            if issubclass(annotated_type, primitive_type):
                return primitive_type
        return annotated_type

    return tuple(map(_transform, annotated_types))
