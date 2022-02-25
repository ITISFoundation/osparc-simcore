from typing import Dict, Tuple, Union, get_args, get_origin


def get_types(annotation) -> Tuple:
    # WARNING: use for testing ONLY

    assert get_origin(Dict[str, int]) is dict  # nosec
    assert get_args(Dict[int, str]) == (int, str)  # nosec
    assert get_origin(Union[int, str]) is Union  # nosec
    assert get_args(Union[int, str]) == (int, str)  # nosec

    if get_origin(annotation) is Union:
        annotated_types = get_args(annotation)
    else:
        annotated_types = (annotation,)

    def _transform(annotated_type):
        for primitive_type in (float, bool, int, str):
            try:
                if issubclass(annotated_type, primitive_type):
                    return primitive_type
            except TypeError:
                # List[Any] or Dict[str, Any]
                pass

        return annotated_type

    return tuple(map(_transform, annotated_types))
