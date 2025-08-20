import importlib
import json


def encode_error_types(
    error_types: tuple[type[BaseException], ...],
) -> str:
    """Encode a tuple of error types into a JSON string."""
    return json.dumps(
        [[error_type.__module__, error_type.__name__] for error_type in error_types]
    )


def decode_error_types(encoded_errors: str) -> tuple[type[BaseException], ...]:
    """Decode a JSON string into a tuple of error types."""
    if not encoded_errors:
        return ()

    error_types_list = json.loads(encoded_errors)
    return tuple(
        getattr(importlib.import_module(module), name)
        for module, name in error_types_list
    )
